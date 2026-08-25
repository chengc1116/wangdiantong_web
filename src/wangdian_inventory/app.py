"""Framework-free HTTP application for the WangDian inventory dashboard."""

import argparse
import csv
import io
import json
import mimetypes
import posixpath
import urllib.parse
import webbrowser
from datetime import date, timedelta
from pathlib import Path
from threading import Timer
from typing import Optional
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .config import Settings, load_settings
from .db import InventoryDatabase
from .report_export import build_daily, build_weekly
from .sync import InventorySynchronizer


def _save_daily_report(database: InventoryDatabase, report_date: date) -> Path:
    """Build the scheduled daily workbook in the project's outputs folder."""
    project_root = Path(__file__).resolve().parents[2]
    output_directory = project_root / "outputs" / f"daily-report-{report_date.isoformat()}"
    output_directory.mkdir(parents=True, exist_ok=True)
    output_path = output_directory / f"wangdian-supply-chain-daily-{report_date.isoformat()}.xlsx"
    output_path.write_bytes(build_daily(database, report_date))
    return output_path


def _parse_date(value: Optional[str], fallback: date) -> date:
    if not value:
        return fallback
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"invalid date: {value}") from exc


def _parse_positive_int(value: Optional[str], fallback: int, maximum: int) -> int:
    try:
        parsed = int(value) if value else fallback
    except ValueError as exc:
        raise ValueError("invalid pagination value") from exc
    if parsed < 1 or parsed > maximum:
        raise ValueError("pagination value out of range")
    return parsed


class InventoryApplication:
    """Small framework-free application wrapper used by the HTTP handler and tests."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or load_settings()
        self.database = InventoryDatabase(self.settings.database_path)
        if self.settings.demo_mode:
            self.database.seed_demo()

    def json_status(self) -> dict:
        return {
            "configured": self.settings.credentials_configured,
            "demo_mode": self.settings.demo_mode,
            "environment": self.settings.environment,
            "database": str(self.settings.database_path),
            "last_sync": self.database.last_sync(),
        }

    def dashboard(self, query: dict) -> tuple[dict, int]:
        today = date.today()
        try:
            start = _parse_date(query.get("start"), today - timedelta(days=29))
            end = _parse_date(query.get("end"), today)
            if start > end:
                raise ValueError("start date must not be after end date")
            if (end - start).days > 366:
                raise ValueError("date range cannot exceed 367 days")
            page = _parse_positive_int(query.get("page"), 1, 100_000)
            page_size = _parse_positive_int(query.get("page_size"), 100, 2000)
            stock_status = query.get("stock_status", "").strip()
            if stock_status not in {"", "positive", "zero", "negative", "unavailable"}:
                raise ValueError("invalid stock status")
            return self.database.dashboard(
                start.isoformat(),
                end.isoformat(),
                search=query.get("search", "").strip(),
                warehouse_id=query.get("warehouse", "").strip(),
                stock_status=stock_status,
                limit=page_size,
                offset=(page - 1) * page_size,
            ), 200
        except ValueError as exc:
            return {"error": str(exc)}, 400

    def sku_detail(self, sku_no: str, query: dict) -> tuple[dict, int]:
        today = date.today()
        try:
            start = _parse_date(query.get("start"), today - timedelta(days=29))
            end = _parse_date(query.get("end"), today)
        except ValueError as exc:
            return {"error": str(exc)}, 400
        result = self.database.sku_detail(sku_no, start.isoformat(), end.isoformat())
        return ({"error": "SKU not found"}, 404) if result is None else (result, 200)

    def warehouse_sales(self, query: dict) -> tuple[dict, int]:
        today = date.today()
        try:
            start = _parse_date(query.get("start"), today - timedelta(days=1))
            end = _parse_date(query.get("end"), start)
            if start > end or (end - start).days > 31:
                raise ValueError("sales date range must be between 1 and 32 days")
            page = _parse_positive_int(query.get("page"), 1, 100_000)
            page_size = _parse_positive_int(query.get("page_size"), 100, 2000)
            return self.database.warehouse_sku_sales(
                start.isoformat(),
                end.isoformat(),
                search=query.get("search", "").strip(),
                warehouse_id=query.get("warehouse", "").strip(),
                limit=page_size,
                offset=(page - 1) * page_size,
            ), 200
        except ValueError as exc:
            return {"error": str(exc)}, 400

    def short_name_sales(self, query: dict) -> tuple[dict, int]:
        today = date.today()
        try:
            start = _parse_date(query.get("start"), today - timedelta(days=1))
            end = _parse_date(query.get("end"), start)
            if start > end or (end - start).days > 31:
                raise ValueError("sales date range must be between 1 and 32 days")
            page = _parse_positive_int(query.get("page"), 1, 100_000)
            page_size = _parse_positive_int(query.get("page_size"), 100, 2000)
            return self.database.short_name_sales(
                start.isoformat(),
                end.isoformat(),
                search=query.get("search", "").strip(),
                limit=page_size,
                offset=(page - 1) * page_size,
            ), 200
        except ValueError as exc:
            return {"error": str(exc)}, 400

    def shop_sales(self, query: dict) -> tuple[dict, int]:
        today = date.today()
        try:
            start = _parse_date(query.get("start"), today - timedelta(days=1))
            end = _parse_date(query.get("end"), start)
            if start > end or (end - start).days > 366:
                raise ValueError("shop sales date range must be between 1 and 367 days")
            page = _parse_positive_int(query.get("page"), 1, 100_000)
            page_size = _parse_positive_int(query.get("page_size"), 100, 2000)
            return self.database.shop_sku_sales(
                start.isoformat(), end.isoformat(),
                search=query.get("search", "").strip(),
                shop_no=query.get("shop", "").strip(),
                warehouse_id=query.get("warehouse", "").strip(),
                limit=page_size,
                offset=(page - 1) * page_size,
            ), 200
        except ValueError as exc:
            return {"error": str(exc)}, 400

    def inbound(self, query: dict) -> tuple[dict, int]:
        today = date.today()
        try:
            end = _parse_date(query.get("end"), today - timedelta(days=1))
            start = _parse_date(query.get("start"), end - timedelta(days=6))
            if start > end or (end - start).days > 366:
                raise ValueError("inbound date range must be between 1 and 367 days")
            page = _parse_positive_int(query.get("page"), 1, 100_000)
            page_size = _parse_positive_int(query.get("page_size"), 100, 2000)
            inbound_type = None
            if query.get("inbound_type"):
                try:
                    inbound_type = int(query["inbound_type"])
                except ValueError as exc:
                    raise ValueError("invalid inbound type") from exc
                if inbound_type <= 0:
                    raise ValueError("invalid inbound type")
            return self.database.inbound_analysis(
                start.isoformat(),
                end.isoformat(),
                search=query.get("search", "").strip(),
                warehouse_id=query.get("warehouse", "").strip(),
                inbound_type=inbound_type,
                limit=page_size,
                offset=(page - 1) * page_size,
            ), 200
        except ValueError as exc:
            return {"error": str(exc)}, 400

    def replenishment(self, query: dict) -> tuple[dict, int]:
        return self._inventory_plan(query, mode="replenishment")

    def purchase_plan(self, query: dict) -> tuple[dict, int]:
        today = date.today()
        try:
            end = _parse_date(query.get("end"), today - timedelta(days=1))
            start = _parse_date(query.get("start"), end - timedelta(days=6))
            if start > end or (end - start).days > 31:
                raise ValueError("analysis date range must be between 1 and 32 days")
            page = _parse_positive_int(query.get("page"), 1, 100_000)
            page_size = _parse_positive_int(query.get("page_size"), 100, 2000)
            target_days = _parse_positive_int(query.get("target_days"), 30, 365)
            trend_min = self._parse_optional_number(query.get("trend_min"), "trend_min")
            trend_max = self._parse_optional_number(query.get("trend_max"), "trend_max")
            if trend_min is not None and trend_max is not None and trend_min >= trend_max:
                raise ValueError("trend_min must be less than trend_max")
            plan_status = query.get("plan_status", "").strip()
            valid_plan_statuses = {
                "", "交期内预计缺货", "应立即下单", "计划下单", "暂不下单",
                "暂无销量", "参数待补充", "建议调拨", "调拨后仍缺货",
            }
            if plan_status not in valid_plan_statuses:
                raise ValueError("invalid plan_status")
            return self.database.purchase_plan(
                start.isoformat(),
                end.isoformat(),
                search=query.get("search", "").strip(),
                limit=page_size,
                offset=(page - 1) * page_size,
                target_days=target_days,
                trend_min=trend_min,
                trend_max=trend_max,
                plan_status=plan_status,
                warehouse_id=query.get("warehouse", "").strip(),
            ), 200
        except ValueError as exc:
            return {"error": str(exc)}, 400

    def transfer_plan(self, query: dict) -> tuple[dict, int]:
        """Return only recommended inter-warehouse transfers for the planning period."""
        today = date.today()
        try:
            end = _parse_date(query.get("end"), today - timedelta(days=1))
            start = _parse_date(query.get("start"), end - timedelta(days=6))
            if start > end or (end - start).days > 31:
                raise ValueError("analysis date range must be between 1 and 32 days")
            page = _parse_positive_int(query.get("page"), 1, 100_000)
            page_size = _parse_positive_int(query.get("page_size"), 100, 2000)
            return self.database.transfer_plan(
                start.isoformat(),
                end.isoformat(),
                search=query.get("search", "").strip(),
                warehouse_id=query.get("warehouse", "").strip(),
                limit=page_size,
                offset=(page - 1) * page_size,
            ), 200
        except ValueError as exc:
            return {"error": str(exc)}, 400

    @staticmethod
    def _parse_optional_number(value: Optional[str], name: str) -> Optional[float]:
        if value in (None, ""):
            return None
        try:
            return float(value)
        except ValueError as exc:
            raise ValueError(f"invalid {name}") from exc

    def clearance(self, query: dict) -> tuple[dict, int]:
        return self._inventory_plan(query, mode="clearance")

    def clearance_summary(self, query: dict) -> tuple[dict, int]:
        try:
            page = _parse_positive_int(query.get("page"), 1, 100_000)
            page_size = _parse_positive_int(query.get("page_size"), 100, 2000)
            return self.database.clearance_summary(
                search=query.get("search", "").strip(),
                warehouse_id=query.get("warehouse", "").strip(),
                limit=page_size,
                offset=(page - 1) * page_size,
            ), 200
        except ValueError as exc:
            return {"error": str(exc)}, 400

    def _inventory_plan(self, query: dict, *, mode: str) -> tuple[dict, int]:
        today = date.today()
        try:
            end = _parse_date(query.get("end"), today - timedelta(days=1))
            start = _parse_date(query.get("start"), end - timedelta(days=6))
            if start > end or (end - start).days > 31:
                raise ValueError("analysis date range must be between 1 and 32 days")
            page = _parse_positive_int(query.get("page"), 1, 100_000)
            page_size = _parse_positive_int(query.get("page_size"), 100, 2000)
            target_days = _parse_positive_int(query.get("target_days"), 30, 365)
            clearance_status = query.get("clearance_status", "").strip()
            alert_status = query.get("alert_status", "").strip()
            alert_mode = query.get("alert_mode", "").strip()
            if mode == "clearance" and clearance_status not in {"", "in_progress", "stagnant", "transit", "cleared"}:
                raise ValueError("invalid clearance status")
            if mode == "replenishment" and alert_mode not in {"", "normal", "clearance"}:
                raise ValueError("invalid alert mode")
            if mode == "replenishment" and alert_status not in {
                "", "库存预警", "中度积压", "严重积压", "清仓预警",
            }:
                raise ValueError("invalid alert status")
            return self.database.replenishment_analysis(
                start.isoformat(),
                end.isoformat(),
                mode=mode,
                search=query.get("search", "").strip(),
                limit=page_size,
                offset=(page - 1) * page_size,
                target_days=target_days,
                clearance_status=clearance_status,
                alert_status=alert_status,
                alert_mode=alert_mode,
                warehouse_id=query.get("warehouse", "").strip(),
            ), 200
        except ValueError as exc:
            return {"error": str(exc)}, 400

    def sync(self, body: dict) -> tuple[dict, int]:
        if not self.settings.credentials_configured:
            return {
                "error": "请先在 examples/wangdian_config.py 中配置旺店通凭证",
                "demo_mode": self.settings.demo_mode,
            }, 409
        try:
            synchronizer = InventorySynchronizer(self.settings, self.database)
            if body.get("scope") == "inventory":
                return synchronizer.sync_inventory_only(), 200
            sync_date = _parse_date(body.get("date"), date.today() - timedelta(days=1))
            return synchronizer.sync_day(sync_date), 200
        except RuntimeError as exc:
            return {"error": str(exc)}, 409
        except Exception as exc:
            return {"error": str(exc)}, 502

    def export_csv(self, query: dict) -> tuple[str, str, int]:
        today = date.today()
        try:
            start = _parse_date(query.get("start"), today - timedelta(days=29))
            end = _parse_date(query.get("end"), today)
            result = self.database.dashboard(
                start.isoformat(), end.isoformat(),
                search=query.get("search", "").strip(),
                warehouse_id=query.get("warehouse", "").strip(),
                stock_status=query.get("stock_status", "").strip(),
                limit=100000,
            )
        except ValueError as exc:
            return json.dumps({"error": str(exc)}, ensure_ascii=False), "application/json", 400
        stream = io.StringIO()
        stream.write("\ufeff")
        writer = csv.writer(stream)
        writer.writerow(["商家编码", "货品名称", "规格", "当前库存", "可用库存", "销售出库", "退货入库", "净发货销量", "采购入库", "实际销售额", "实退金额", "净销售额", "零售价估算额", "可售天数"])
        for item in result["items"]:
            writer.writerow([item["sku_no"], item["goods_name"], item["spec_name"], item["stock_num"], item["available_num"], item["sales_qty"], item["return_qty"], item["net_sales_qty"], item["purchase_qty"], item["sales_amount"], item["refund_amount"], item["net_revenue"], item["estimated_revenue"], item["days_cover"] if item["days_cover"] is not None else ""])
        return stream.getvalue(), "text/csv; charset=utf-8", 200

    def export_report(self, report_type: str, query: dict) -> tuple[bytes, int, str]:
        try:
            if report_type not in {"daily", "weekly"}:
                raise ValueError("invalid report type")
            end = _parse_date(query.get("date"), date.today() - timedelta(days=1))
            content = build_daily(self.database, end) if report_type == "daily" else build_weekly(self.database, end)
            filename = f"wangdian-supply-chain-{report_type}-{end.isoformat()}.xlsx"
            return content, 200, filename
        except ValueError as exc:
            return json.dumps({"error": str(exc)}, ensure_ascii=False).encode("utf-8"), 400, "error.json"


class InventoryHandler(BaseHTTPRequestHandler):
    """Serve the dashboard assets and JSON endpoints."""

    application: InventoryApplication
    static_root = Path(__file__).resolve().parent

    def log_message(self, format: str, *args: object) -> None:
        return

    def send_payload(self, payload: bytes, content_type: str, status: int = 200, headers: Optional[dict] = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(payload)

    def send_json(self, value: object, status: int = 200) -> None:
        self.send_payload(json.dumps(value, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8", status)

    def query(self) -> dict:
        parsed = urllib.parse.urlparse(self.path)
        return {key: values[-1] for key, values in urllib.parse.parse_qs(parsed.query).items() if values}

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = self.query()
        if path == "/":
            html = (self.static_root / "templates" / "index.html").read_text(encoding="utf-8")
            # Bump the asset query string when the page contract changes so an
            # already-open dashboard cannot keep rendering an older bundle.
            html = html.replace("{{ url_for('static', filename='app.css') }}", "/static/app.css?v=20260824").replace("{{ url_for('static', filename='app.js') }}", "/static/app.js?v=20260824")
            self.send_payload(html.encode("utf-8"), "text/html; charset=utf-8")
            return
        if path.startswith("/static/"):
            filename = posixpath.normpath(path.removeprefix("/static/"))
            if filename.startswith("../") or filename == "..":
                self.send_json({"error": "not found"}, 404)
                return
            file_path = self.static_root / "static" / filename
            if not file_path.is_file():
                self.send_json({"error": "not found"}, 404)
                return
            content_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
            self.send_payload(file_path.read_bytes(), content_type)
            return
        if path == "/api/status":
            self.send_json(self.application.json_status())
        elif path == "/api/warehouses":
            self.send_json({"items": self.application.database.warehouses()})
        elif path == "/api/dashboard":
            payload, status = self.application.dashboard(query)
            self.send_json(payload, status)
        elif path == "/api/warehouse-sales":
            payload, status = self.application.warehouse_sales(query)
            self.send_json(payload, status)
        elif path == "/api/inbound":
            payload, status = self.application.inbound(query)
            self.send_json(payload, status)
        elif path == "/api/short-name-sales":
            payload, status = self.application.short_name_sales(query)
            self.send_json(payload, status)
        elif path == "/api/shop-sales":
            payload, status = self.application.shop_sales(query)
            self.send_json(payload, status)
        elif path == "/api/replenishment":
            payload, status = self.application.replenishment(query)
            self.send_json(payload, status)
        elif path == "/api/purchase-plan":
            payload, status = self.application.purchase_plan(query)
            self.send_json(payload, status)
        elif path == "/api/transfer-plan":
            payload, status = self.application.transfer_plan(query)
            self.send_json(payload, status)
        elif path == "/api/clearance":
            payload, status = self.application.clearance(query)
            self.send_json(payload, status)
        elif path == "/api/clearance-summary":
            payload, status = self.application.clearance_summary(query)
            self.send_json(payload, status)
        elif path.startswith("/api/skus/"):
            sku_no = urllib.parse.unquote(path.removeprefix("/api/skus/"))
            payload, status = self.application.sku_detail(sku_no, query)
            self.send_json(payload, status)
        elif path == "/api/export.csv":
            payload, content_type, status = self.application.export_csv(query)
            filename = f"wangdian-inventory-{query.get('start', date.today().isoformat())}-{query.get('end', date.today().isoformat())}.csv"
            self.send_payload(payload.encode("utf-8"), content_type, status, {"Content-Disposition": f'attachment; filename="{filename}"'})
        elif path == "/api/reports/daily.xlsx":
            payload, status, filename = self.application.export_report("daily", query)
            self.send_payload(payload, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", status, {"Content-Disposition": f'attachment; filename="{filename}"'})
        elif path == "/api/reports/weekly.xlsx":
            payload, status, filename = self.application.export_report("weekly", query)
            self.send_payload(payload, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", status, {"Content-Disposition": f'attachment; filename="{filename}"'})
        else:
            self.send_json({"error": "not found"}, 404)

    def do_POST(self) -> None:
        if urllib.parse.urlparse(self.path).path != "/api/sync":
            self.send_json({"error": "not found"}, 404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            if not isinstance(body, dict):
                body = {}
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
            self.send_json({"error": "invalid JSON body"}, 400)
            return
        payload, status = self.application.sync(body)
        self.send_json(payload, status)


def create_app(settings: Optional[Settings] = None) -> InventoryApplication:
    return InventoryApplication(settings)


def main() -> None:
    parser = argparse.ArgumentParser(description="WangDian inventory dashboard")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5050)
    parser.add_argument(
        "--lan",
        action="store_true",
        help="listen on all network interfaces for LAN access (equivalent to --host 0.0.0.0)",
    )
    parser.add_argument("--sync", metavar="YYYY-MM-DD", help="sync one day and exit")
    parser.add_argument(
        "--backfill-shop-sales",
        nargs=2,
        metavar=("START_DATE", "END_DATE"),
        help="backfill shipment orders with shop fields, dates are YYYY-MM-DD",
    )
    parser.add_argument(
        "--daily-sync",
        action="store_true",
        help="fully sync yesterday's movements, sales, returns, cancellations, goods and current inventory, then exit",
    )
    parser.add_argument(
        "--daily-job",
        action="store_true",
        help="fully sync yesterday and save its daily Excel report, then exit",
    )
    parser.add_argument(
        "--inventory-sync",
        action="store_true",
        help="refresh all current inventory and exit",
    )
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    settings = load_settings()
    database = InventoryDatabase(settings.database_path)
    if settings.demo_mode:
        database.seed_demo()
    if args.sync:
        result = InventorySynchronizer(settings, database).sync_day(date.fromisoformat(args.sync))
        print(result)
        return
    if args.backfill_shop_sales:
        start_date, end_date = (date.fromisoformat(value) for value in args.backfill_shop_sales)
        result = InventorySynchronizer(settings, database).backfill_shop_sales(start_date, end_date)
        print(json.dumps(result, ensure_ascii=False))
        return
    if args.daily_sync:
        result = InventorySynchronizer(settings, database).sync_day(date.today() - timedelta(days=1))
        print(json.dumps(result, ensure_ascii=False))
        return
    if args.daily_job:
        report_date = date.today() - timedelta(days=1)
        result = InventorySynchronizer(settings, database).sync_day(report_date)
        output_path = _save_daily_report(database, report_date)
        result["report_path"] = str(output_path)
        print(json.dumps(result, ensure_ascii=False))
        return
    if args.inventory_sync:
        result = InventorySynchronizer(settings, database).sync_inventory_only()
        print(json.dumps(result, ensure_ascii=False))
        return
    if args.lan:
        args.host = "0.0.0.0"
    application = create_app(settings)
    InventoryHandler.application = application
    url = f"http://{args.host}:{args.port}"
    if not args.no_browser:
        Timer(0.8, lambda: webbrowser.open(url)).start()
    server = ThreadingHTTPServer((args.host, args.port), InventoryHandler)
    print(f"旺店通库存台运行于 {url}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
