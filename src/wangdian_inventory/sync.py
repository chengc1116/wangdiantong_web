"""Daily synchronization from WangDian OpenAPI into SQLite."""

import json
import re
from datetime import date, datetime, time, timedelta
from itertools import islice
from threading import Lock
from collections import Counter, defaultdict
from typing import Any, Callable, Dict, Iterator, List, Mapping, Optional, Sequence

from wangdian import WangdianClient

from .config import Settings
from .db import InventoryDatabase, movement_key


SYNC_LOCK = Lock()


def _chunks(values: Sequence[str], size: int) -> Iterator[Sequence[str]]:
    iterator = iter(values)
    while chunk := list(islice(iterator, size)):
        yield chunk


class InventorySynchronizer:
    # MVP scope: initialize from July 2026 instead of scanning the full ERP history.
    INITIAL_INVENTORY_START = datetime(2026, 7, 1)

    def __init__(self, settings: Settings, database: InventoryDatabase) -> None:
        if not settings.credentials_configured:
            raise ValueError("WangDian credentials are not configured")
        self.settings = settings
        self.database = database

    def client(self) -> WangdianClient:
        return WangdianClient(
            sid=self.settings.sid,
            app_key=self.settings.app_key,
            app_secret=self.settings.app_secret,
            environment=self.settings.environment,
            timeout=(10, 60),
            # WangDian's free API limit is 60 requests per minute. Leave a
            # small margin so a scheduled sync does not sit on the boundary.
            requests_per_minute=50,
        )

    @staticmethod
    def _paginate(
        client: WangdianClient,
        endpoint: str,
        parameters: Mapping[str, Any],
        result_key: str,
        *,
        page_size: int,
        max_pages: int = 10000,
    ) -> Iterator[Dict[str, Any]]:
        page_no = 0
        while page_no < max_pages:
            payload = dict(parameters)
            payload.update({"page_no": page_no, "page_size": page_size})
            response = client.call(endpoint, payload)
            records = response.get(result_key) or []
            if not isinstance(records, list):
                raise ValueError(f"{endpoint} returned a non-list {result_key}")
            for record in records:
                if isinstance(record, dict):
                    yield record
            if not records or len(records) < page_size:
                return
            total = response.get("total_count")
            if total not in (None, "", -1, "-1"):
                try:
                    if (page_no + 1) * page_size >= int(total):
                        return
                except (TypeError, ValueError):
                    pass
            page_no += 1
        raise RuntimeError(f"{endpoint} exceeded the pagination safety limit")

    def sync_goods(
        self, client: WangdianClient, sync_date: Optional[date] = None, *, full: bool = False
    ) -> int:
        # The Web API requires a SKU or a time range for goods_query. On a
        # brand-new database, movement rows will seed the product table first.
        if not self.database.product_skus():
            return 0
        parameters: Dict[str, Any] = {}
        if not full:
            effective_date = sync_date or date.today()
            parameters = {
                "start_time": datetime.combine(effective_date, time.min),
                "end_time": datetime.combine(effective_date, time.max.replace(microsecond=0)),
            }
        goods = self._paginate(
            client, "goods_query", parameters, "goods_list", page_size=500
        )
        specs: List[Dict[str, Any]] = []
        count = 0
        for goods_item in goods:
            for spec in goods_item.get("spec_list") or []:
                if not isinstance(spec, dict):
                    continue
                merged = dict(spec)
                merged["goods_no"] = merged.get("goods_no") or goods_item.get("goods_no")
                merged["goods_name"] = merged.get("goods_name") or goods_item.get("goods_name")
                merged["short_name"] = merged.get("short_name") or goods_item.get("short_name")
                merged["brand_name"] = merged.get("brand_name") or goods_item.get("brand_name")
                # WangDian exposes two different remark levels. The report's
                # 规格备注 comes only from spec_list[].remark; goods.remark is
                # stored separately as 货品备注 and must not fall back into the
                # SKU/spec field when the SKU remark is empty.
                merged["spec_remark"] = str(spec.get("remark") or "").strip()
                merged["goods_remark"] = str(goods_item.get("remark") or "").strip()
                if spec.get("prop1") not in (None, ""):
                    merged["erp_price"] = spec.get("prop1")
                # WangDian exposes the planning metadata as positional props.
                # Production days are normally goods-level prop3, while line,
                # capacity and structure are commonly spec-level prop4/prop5/prop3.
                for index in range(1, 11):
                    key = f"goods_prop{index}"
                    if goods_item.get(f"prop{index}") not in (None, ""):
                        merged[key] = goods_item.get(f"prop{index}")
                goods_prop3 = str(goods_item.get("prop3") or "").strip()
                spec_prop3 = str(spec.get("prop3") or "").strip()
                production_text = goods_prop3 if re.search(r"\d", goods_prop3) else (
                    spec_prop3 if re.search(r"\d", spec_prop3) else ""
                )
                if production_text:
                    merged["production_days"] = production_text
                structure = spec_prop3 if spec_prop3 and not re.search(r"\d", spec_prop3) else str(goods_item.get("prop2") or "").strip()
                if structure:
                    merged["product_structure"] = structure
                line_value = str(spec.get("prop4") or goods_item.get("prop4") or "").strip()
                capacity_value = str(spec.get("prop5") or goods_item.get("prop5") or "").strip()
                merged["production_line"] = line_value if "产线" in line_value else ""
                merged["production_capacity"] = capacity_value if ("产能" in capacity_value or "日产能" in capacity_value) else ""
                specs.append(merged)
                if len(specs) >= 500:
                    count += self.database.upsert_products(specs)
                    specs.clear()
        count += self.database.upsert_products(specs)
        mark_clearance = getattr(self.database, "mark_clearance_products_from_remarks", None)
        if callable(mark_clearance):
            mark_clearance()
        return count

    def sync_movements(self, client: WangdianClient, sync_date: date) -> int:
        parameters = {
            "start_time": datetime.combine(sync_date, time.min),
            "end_time": datetime.combine(sync_date, time.max.replace(microsecond=0)),
        }
        records = list(self._paginate(
            client,
            "stock_detail_report_query",
            parameters,
            "data",
            page_size=100,
        ))

        # The formal API has returned identical rows for the same movement
        # (for example JY2607302405, twice for 8 units).  The ERP report counts
        # both rows.  Preserve that response-level occurrence while keeping a
        # normal repeated sync idempotent.
        base_counts = Counter(movement_key(record) for record in records)
        occurrences = defaultdict(int)
        normalized_records: List[Dict[str, Any]] = []
        for record in records:
            base_key = movement_key(record)
            if base_counts[base_key] > 1:
                normalized = dict(record)
                normalized["_api_duplicate_index"] = occurrences[base_key]
                occurrences[base_key] += 1
                normalized_records.append(normalized)
            else:
                normalized_records.append(record)
        batch: List[Dict[str, Any]] = []
        count = 0
        product_batch: List[Dict[str, Any]] = []
        for record in normalized_records:
            batch.append(record)
            product_batch.append(record)
            if len(batch) >= 500:
                count += self.database.upsert_movements(batch)
                self.database.upsert_products(product_batch)
                batch.clear()
                product_batch.clear()
        count += self.database.upsert_movements(batch)
        self.database.upsert_products(product_batch)
        return count

    def sync_warehouses(self, client: WangdianClient) -> int:
        warehouses: List[Dict[str, Any]] = []
        for disabled in (0, 1):
            warehouses.extend(
                self._paginate(
                    client,
                    "warehouse_query",
                    {"is_disabled": disabled},
                    "warehouses",
                    page_size=100,
                )
            )
        return self.database.upsert_warehouses(warehouses)

    def sync_sales(self, client: WangdianClient, sync_date: date) -> int:
        parameters = {
            "start_time": datetime.combine(sync_date, time.min),
            "end_time": datetime.combine(sync_date, time.max.replace(microsecond=0)),
            "time_type": 2,
        }
        orders = self._paginate(
            client,
            "stockout_order_query_trade",
            parameters,
            "stockout_list",
            page_size=100,
        )
        batch: List[Dict[str, Any]] = []
        count = 0
        for order in orders:
            batch.append(order)
            if len(batch) >= 100:
                count += self.database.upsert_sales_orders(batch)
                batch.clear()
        count += self.database.upsert_sales_orders(batch)
        return count

    def backfill_shop_sales(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Backfill store-level shipment orders by consign time, one day at a time."""
        if end_date < start_date:
            raise ValueError("end_date must not be before start_date")
        if not SYNC_LOCK.acquire(blocking=False):
            raise RuntimeError("another synchronization is already running")
        result: Dict[str, Any] = {"start": start_date.isoformat(), "end": end_date.isoformat(), "days": []}
        try:
            current = start_date
            with self.client() as client:
                while current <= end_date:
                    count = self.sync_sales(client, current)
                    result["days"].append({"date": current.isoformat(), "sales_line_count": count})
                    current += timedelta(days=1)
            result["sales_line_count"] = sum(day["sales_line_count"] for day in result["days"])
            return result
        finally:
            SYNC_LOCK.release()

    def sync_returns(self, client: WangdianClient, sync_date: date) -> int:
        parameters = {
            "start_time": datetime.combine(sync_date, time.min),
            "end_time": datetime.combine(sync_date, time.max.replace(microsecond=0)),
        }
        orders = self._paginate(
            client,
            "stockin_order_query_refund",
            parameters,
            "stockin_list",
            page_size=100,
        )
        batch: List[Dict[str, Any]] = []
        count = 0
        for order in orders:
            batch.append(order)
            if len(batch) >= 100:
                count += self.database.upsert_return_orders(batch)
                batch.clear()
        count += self.database.upsert_return_orders(batch)
        return count

    def sync_cancellations(self, client: WangdianClient, sync_date: date) -> int:
        parameters = {
            "start_time": datetime.combine(sync_date, time.min),
            "end_time": datetime.combine(sync_date, time.max.replace(microsecond=0)),
        }
        orders = self._paginate(
            client,
            "stockout_order_query_trade_cancel",
            parameters,
            "stockout_list",
            page_size=100,
        )
        return self.database.update_sales_statuses(orders)

    def sync_inventory(
        self,
        client: WangdianClient,
        progress: Optional[Callable[[int, datetime, datetime, int, int], None]] = None,
        *,
        full: bool = False,
    ) -> int:
        skus = self.database.product_skus()
        all_records: List[Dict[str, Any]] = []
        snapshot_date = date.today().isoformat()
        if full or not skus:
            window_start = self.INITIAL_INVENTORY_START
            final_end = datetime.now().replace(microsecond=0)
            window_size = timedelta(days=29, hours=23, minutes=59, seconds=59)
            window_number = 0
            while window_start <= final_end:
                window_end = min(window_start + window_size, final_end)
                records = list(
                    self._paginate(
                        client,
                        "stock_query",
                        {"start_time": window_start, "end_time": window_end},
                        "stocks",
                        page_size=100,
                    )
                )
                all_records.extend(records)
                window_number += 1
                if progress is not None:
                    progress(window_number, window_start, window_end, len(records), len(all_records))
                window_start = window_end + timedelta(seconds=1)
            return self.database.replace_inventory(all_records, snapshot_date)

        for sku_chunk in _chunks(skus, 200):
            records = self._paginate(
                client,
                "stock_query",
                {
                    "spec_no_list": json.dumps(
                        list(sku_chunk), ensure_ascii=True, separators=(",", ":")
                    )
                },
                "stocks",
                page_size=100,
            )
            all_records.extend(records)
        return self.database.replace_inventory(all_records, snapshot_date)

    def sync_inventory_only(self) -> Dict[str, Any]:
        if not SYNC_LOCK.acquire(blocking=False):
            raise RuntimeError("another synchronization is already running")
        sync_date = date.today().isoformat()
        run_id = self.database.start_sync(sync_date)
        inventory_count = 0
        try:
            with self.client() as client:
                self.sync_warehouses(client)
                inventory_count = self.sync_inventory(client)
            weekly_snapshot_count = 0
            if date.today().weekday() == 0:
                weekly_snapshot_count = self.database.record_clearance_weekly_snapshot(sync_date)
            self.database.finish_sync(
                run_id,
                status="success",
                inventory_count=inventory_count,
            )
            return {
                "status": "success",
                "date": sync_date,
                "inventory_count": inventory_count,
                "clearance_weekly_snapshot_count": weekly_snapshot_count,
                "scope": "inventory",
            }
        except Exception as exc:
            self.database.finish_sync(
                run_id,
                status="failed",
                inventory_count=inventory_count,
                error_message=str(exc),
            )
            raise
        finally:
            SYNC_LOCK.release()

    def sync_operational_day(
        self, sync_date: date, *, refresh_inventory: bool = True
    ) -> Dict[str, Any]:
        """Sync one complete movement day and optionally refresh current stock.

        This is the scheduled MVP path. It stores both stock movements for the
        warehouse-level total and shipment orders for store-level attribution.
        """
        if not SYNC_LOCK.acquire(blocking=False):
            raise RuntimeError("another synchronization is already running")
        run_id = self.database.start_sync(sync_date.isoformat())
        movement_count = 0
        goods_count = 0
        inventory_count = 0
        sales_count = 0
        try:
            with self.client() as client:
                self.sync_movements(client, sync_date)
                sales_count = self.sync_sales(client, sync_date)
                movement_count = self.database.movement_count(sync_date.isoformat())
                goods_count = self.sync_goods(client, sync_date)
                if refresh_inventory:
                    self.sync_warehouses(client)
                    inventory_count = self.sync_inventory(client)
            weekly_snapshot_count = 0
            if refresh_inventory and date.today().weekday() == 0:
                weekly_snapshot_count = self.database.record_clearance_weekly_snapshot(date.today().isoformat())
            self.database.finish_sync(
                run_id,
                status="success",
                movement_count=movement_count,
                inventory_count=inventory_count,
                sales_count=sales_count,
            )
            return {
                "status": "success",
                "date": sync_date.isoformat(),
                "movement_count": movement_count,
                "sales_count": sales_count,
                "goods_count": goods_count,
                "inventory_count": inventory_count,
                "clearance_weekly_snapshot_count": weekly_snapshot_count,
                "scope": "operational_day",
            }
        except Exception as exc:
            self.database.finish_sync(
                run_id,
                status="failed",
                movement_count=movement_count,
                inventory_count=inventory_count,
                error_message=str(exc),
            )
            raise
        finally:
            SYNC_LOCK.release()

    def sync_day(self, sync_date: date) -> Dict[str, Any]:
        if not SYNC_LOCK.acquire(blocking=False):
            raise RuntimeError("another synchronization is already running")
        run_id = self.database.start_sync(sync_date.isoformat())
        movement_count = 0
        inventory_count = 0
        goods_count = 0
        sales_count = 0
        return_count = 0
        cancellation_count = 0
        try:
            with self.client() as client:
                movement_count = self.sync_movements(client, sync_date)
                sales_count = self.sync_sales(client, sync_date)
                cancellation_count = self.sync_cancellations(client, sync_date)
                return_count = self.sync_returns(client, sync_date)
                goods_count = self.sync_goods(client, sync_date)
                inventory_count = self.sync_inventory(client)
            weekly_snapshot_count = 0
            if date.today().weekday() == 0:
                weekly_snapshot_count = self.database.record_clearance_weekly_snapshot(date.today().isoformat())
            self.database.finish_sync(
                run_id,
                status="success",
                movement_count=movement_count,
                inventory_count=inventory_count,
                sales_count=sales_count,
                return_count=return_count,
                cancellation_count=cancellation_count,
            )
            return {
                "status": "success",
                "date": sync_date.isoformat(),
                "goods_count": goods_count,
                "movement_count": movement_count,
                "inventory_count": inventory_count,
                "sales_count": sales_count,
                "return_count": return_count,
                "cancellation_count": cancellation_count,
                "clearance_weekly_snapshot_count": weekly_snapshot_count,
            }
        except Exception as exc:
            self.database.finish_sync(
                run_id,
                status="failed",
                movement_count=movement_count,
                inventory_count=inventory_count,
                sales_count=sales_count,
                return_count=return_count,
                cancellation_count=cancellation_count,
                error_message=str(exc),
            )
            raise
        finally:
            SYNC_LOCK.release()
