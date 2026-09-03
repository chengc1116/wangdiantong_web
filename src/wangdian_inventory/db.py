"""SQLite persistence and dashboard queries."""

import json
import hashlib
import math
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional


PROCUREMENT_WAREHOUSE_NAMES = (
    "主仓库（新）",
    "TMT康复仓",
    "杰菲克德国仓",
    "日本仓",
    "ENYISA仓",
)


SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    sku_no TEXT PRIMARY KEY,
    goods_no TEXT NOT NULL DEFAULT '',
    goods_name TEXT NOT NULL DEFAULT '',
    short_name TEXT NOT NULL DEFAULT '',
    spec_name TEXT NOT NULL DEFAULT '',
    barcode TEXT NOT NULL DEFAULT '',
    unit_name TEXT NOT NULL DEFAULT '',
    supplier_id TEXT NOT NULL DEFAULT '',
    supplier_no TEXT NOT NULL DEFAULT '',
    supplier_name TEXT NOT NULL DEFAULT '',
    supplier_updated_at TEXT NOT NULL DEFAULT '',
    retail_price REAL NOT NULL DEFAULT 0,
    wholesale_price REAL NOT NULL DEFAULT 0,
    purchase_price REAL,
    category TEXT NOT NULL DEFAULT '',
    product_structure TEXT NOT NULL DEFAULT '',
    moq REAL,
    production_days INTEGER,
    production_line TEXT NOT NULL DEFAULT '',
    production_capacity TEXT NOT NULL DEFAULT '',
    spec_remark TEXT NOT NULL DEFAULT '',
    goods_remark TEXT NOT NULL DEFAULT '',
    erp_price REAL,
    metadata_status TEXT NOT NULL DEFAULT '待补充',
    metadata_source TEXT NOT NULL DEFAULT '',
    metadata_updated_at TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL,
    raw_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS warehouse_master (
    warehouse_id TEXT PRIMARY KEY,
    warehouse_no TEXT NOT NULL DEFAULT '',
    warehouse_name TEXT NOT NULL DEFAULT '',
    warehouse_type INTEGER NOT NULL DEFAULT 0,
    is_disabled INTEGER NOT NULL DEFAULT 0,
    role TEXT NOT NULL DEFAULT 'sales',
    transfer_source_enabled INTEGER NOT NULL DEFAULT 0,
    modified TEXT NOT NULL DEFAULT '',
    raw_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS inventory_current (
    sku_no TEXT NOT NULL,
    warehouse_id TEXT NOT NULL DEFAULT '',
    warehouse_no TEXT NOT NULL DEFAULT '',
    warehouse_name TEXT NOT NULL DEFAULT '',
    stock_num REAL NOT NULL DEFAULT 0,
    available_num REAL NOT NULL DEFAULT 0,
    cost_price REAL NOT NULL DEFAULT 0,
    avg_cost_price REAL NOT NULL DEFAULT 0,
    purchase_in_transit_num REAL NOT NULL DEFAULT 0,
    modified TEXT NOT NULL DEFAULT '',
    synced_at TEXT NOT NULL,
    raw_json TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY (sku_no, warehouse_id)
);

CREATE TABLE IF NOT EXISTS inventory_snapshots (
    snapshot_date TEXT NOT NULL,
    sku_no TEXT NOT NULL,
    warehouse_id TEXT NOT NULL DEFAULT '',
    stock_num REAL NOT NULL DEFAULT 0,
    available_num REAL NOT NULL DEFAULT 0,
    cost_price REAL NOT NULL DEFAULT 0,
    purchase_in_transit_num REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (snapshot_date, sku_no, warehouse_id)
);

CREATE TABLE IF NOT EXISTS clearance_weekly_snapshots (
    snapshot_week TEXT NOT NULL,
    snapshot_date TEXT NOT NULL,
    sku_no TEXT NOT NULL,
    warehouse_id TEXT NOT NULL DEFAULT '',
    stock_num REAL NOT NULL DEFAULT 0,
    available_num REAL NOT NULL DEFAULT 0,
    unit_cost REAL NOT NULL DEFAULT 0,
    stock_cost REAL NOT NULL DEFAULT 0,
    purchase_price REAL NOT NULL DEFAULT 0,
    purchase_cost REAL NOT NULL DEFAULT 0,
    recorded_at TEXT NOT NULL,
    PRIMARY KEY (snapshot_week, sku_no, warehouse_id)
);

CREATE INDEX IF NOT EXISTS idx_clearance_weekly_snapshots_date
ON clearance_weekly_snapshots(snapshot_date);

CREATE TABLE IF NOT EXISTS movements (
    movement_key TEXT PRIMARY KEY,
    movement_date TEXT NOT NULL,
    event_time TEXT NOT NULL,
    sku_no TEXT NOT NULL,
    warehouse_id TEXT NOT NULL DEFAULT '',
    warehouse_no TEXT NOT NULL DEFAULT '',
    warehouse_name TEXT NOT NULL DEFAULT '',
    movement_type INTEGER NOT NULL,
    movement_name TEXT NOT NULL DEFAULT '',
    in_num REAL NOT NULL DEFAULT 0,
    out_num REAL NOT NULL DEFAULT 0,
    quantity REAL NOT NULL DEFAULT 0,
    src_order_no TEXT NOT NULL DEFAULT '',
    source_id TEXT NOT NULL DEFAULT '',
    source_detail_id TEXT NOT NULL DEFAULT '',
    raw_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_movements_date ON movements(movement_date);
CREATE INDEX IF NOT EXISTS idx_movements_sku_date ON movements(sku_no, movement_date);
CREATE INDEX IF NOT EXISTS idx_movements_source_detail ON movements(source_detail_id, sku_no);
CREATE INDEX IF NOT EXISTS idx_movements_src_order_sku ON movements(src_order_no, sku_no);

CREATE TABLE IF NOT EXISTS sales_lines (
    sale_key TEXT PRIMARY KEY,
    sale_date TEXT NOT NULL,
    consign_time TEXT NOT NULL,
    sku_no TEXT NOT NULL,
    warehouse_id TEXT NOT NULL DEFAULT '',
    warehouse_no TEXT NOT NULL DEFAULT '',
    warehouse_name TEXT NOT NULL DEFAULT '',
    shop_id TEXT NOT NULL DEFAULT '',
    shop_no TEXT NOT NULL DEFAULT '',
    shop_name TEXT NOT NULL DEFAULT '',
    stockout_id TEXT NOT NULL DEFAULT '',
    detail_id TEXT NOT NULL DEFAULT '',
    source_detail_id TEXT NOT NULL DEFAULT '',
    src_order_no TEXT NOT NULL DEFAULT '',
    order_no TEXT NOT NULL DEFAULT '',
    quantity REAL NOT NULL DEFAULT 0,
    paid_amount REAL NOT NULL DEFAULT 0,
    share_amount REAL NOT NULL DEFAULT 0,
    retail_price REAL NOT NULL DEFAULT 0,
    sell_price REAL NOT NULL DEFAULT 0,
    cost_price REAL NOT NULL DEFAULT 0,
    status INTEGER NOT NULL DEFAULT 0,
    modified TEXT NOT NULL DEFAULT '',
    raw_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_sales_lines_date ON sales_lines(sale_date);
CREATE INDEX IF NOT EXISTS idx_sales_lines_sku_date ON sales_lines(sku_no, sale_date);
CREATE INDEX IF NOT EXISTS idx_sales_lines_source_detail ON sales_lines(source_detail_id, sku_no);
CREATE INDEX IF NOT EXISTS idx_sales_lines_src_order_sku ON sales_lines(src_order_no, sku_no);

CREATE TABLE IF NOT EXISTS return_lines (
    return_key TEXT PRIMARY KEY,
    return_date TEXT NOT NULL,
    stockin_time TEXT NOT NULL,
    sku_no TEXT NOT NULL,
    warehouse_id TEXT NOT NULL DEFAULT '',
    warehouse_no TEXT NOT NULL DEFAULT '',
    warehouse_name TEXT NOT NULL DEFAULT '',
    stockin_id TEXT NOT NULL DEFAULT '',
    detail_id TEXT NOT NULL DEFAULT '',
    source_detail_id TEXT NOT NULL DEFAULT '',
    src_order_no TEXT NOT NULL DEFAULT '',
    order_no TEXT NOT NULL DEFAULT '',
    quantity REAL NOT NULL DEFAULT 0,
    refund_amount REAL NOT NULL DEFAULT 0,
    source_price REAL NOT NULL DEFAULT 0,
    cost_price REAL NOT NULL DEFAULT 0,
    status INTEGER NOT NULL DEFAULT 0,
    modified TEXT NOT NULL DEFAULT '',
    raw_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_return_lines_date ON return_lines(return_date);
CREATE INDEX IF NOT EXISTS idx_return_lines_sku_date ON return_lines(sku_no, return_date);

CREATE TABLE IF NOT EXISTS sync_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sync_date TEXT NOT NULL,
    status TEXT NOT NULL,
    movement_count INTEGER NOT NULL DEFAULT 0,
    inventory_count INTEGER NOT NULL DEFAULT 0,
    sales_count INTEGER NOT NULL DEFAULT 0,
    return_count INTEGER NOT NULL DEFAULT 0,
    cancellation_count INTEGER NOT NULL DEFAULT 0,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    error_message TEXT NOT NULL DEFAULT ''
);
"""


MOVEMENT_TYPES = {
    "采购入库": 1,
    "调拨入库": 2,
    "退货入库": 3,
    "盘盈入库": 4,
    "生产入库": 5,
    "其他入库": 6,
    "委外仓入库": 8,
    "委外入库": 9,
    "委外盘盈入库": 10,
    "直发入库": 11,
    "纠错入库": 15,
    "预入库": 16,
    "移位上架": 20,
    "销售订单": -1,
    "销售出库": -1,
    "调拨出库": -2,
    "采购退货出库": -3,
    "盘亏出库": -4,
    "生产出库": -5,
    "现款销售出库": -6,
    "其他出库": -7,
    "委外仓出库": -8,
    "委外出库": -9,
    "委外盘亏出库": -10,
    "纠错出库": -15,
    "移位下架": -20,
}


# Imported from 停用仓列表.xlsx on 2026-08-13. These warehouses are kept in
# raw history for audit, but excluded from operational stock, sales and planning.
DISABLED_WAREHOUSE_NAMES = (
    "2589648-2589648", "主仓库", "虚拟仓", "护具厂家仓库", "T1", "T2", "阿里健康仓",
    "TRIGGER POINT仓", "SKLZ仓", "HARBINGER仓", "宁波备用仓", "赠品仓", "户外用品仓停止销售",
    "拼多多仓", "微信渠道", "一楼库位", "京东POP仓", "三楼仓库", "配件仓",
    "宁波灵动10仓库", "宁波炫动者12仓", "东莞分仓", "爆款仓1", "爆款仓（新）",
    "进口仓（新）", "抖音蹦床分仓", "速卖通仓", "阿里巴巴云仓", "阿里巴巴云仓次品",
)


def movement_type(item: Mapping[str, Any]) -> int:
    value = item.get("in_out_type")
    if value not in (None, ""):
        label = str(value).strip()
        if label in MOVEMENT_TYPES:
            return MOVEMENT_TYPES[label]
        try:
            return int(float(label))
        except ValueError:
            pass

    # Older/demo payloads may only contain src_order_type. This is a fallback,
    # not the primary classification field documented by WangDian.
    source_type = int(to_float(item.get("src_order_type")))
    if to_float(item.get("out_num")) != 0:
        return -1 if source_type in (1, 98, 99) else -abs(source_type or 999)
    return abs(source_type or 999)


def movement_key(item: Mapping[str, Any]) -> str:
    # One source detail can be split across warehouses, positions or batches.
    # Include those dimensions so valid split rows are not treated as duplicates.
    identity_fields = (
        "src_id",
        "src_detail_id",
        "rec_id",
        "create_date",
        "modified",
        "sku_no",
        "spec_no",
        "warehouse_id",
        "warehouse_no",
        "in_out_type",
        "src_order_no",
        "stockin_no",
        "stockout_no",
        "position_id",
        "position_no",
        "batch_no",
        "production_date",
        "expire_date",
        "stock_type",
        "log_type",
        "in_num",
        "out_num",
        "num",
        "cost_price",
    )
    identity = {field: item.get(field) for field in identity_fields}
    # A few formal API responses contain byte-for-byte repeated movement rows.
    # The synchronizer assigns an occurrence number only within that response
    # so those rows can be retained without making ordinary re-syncs additive.
    duplicate_index = item.get("_api_duplicate_index")
    if duplicate_index not in (None, ""):
        identity["_api_duplicate_index"] = int(duplicate_index)
    encoded = json.dumps(
        identity, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def to_float(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    try:
        result = float(value)
        return result if math.isfinite(result) else 0.0
    except (TypeError, ValueError):
        return 0.0


def inventory_number(value: Any) -> float:
    number = to_float(value)
    # WangDian test data can contain sentinel-like values around -1e11. Keep
    # ordinary negative inventory, but do not let impossible sentinels corrupt totals.
    return 0.0 if abs(number) > 1_000_000_000 else number


def _round_purchase_qty_to_50(quantity: int) -> int:
    """Round a positive purchase quantity to a 50-unit multiple.

    A remainder of 11 or more rounds up; 10 or less rounds down, matching the
    procurement rule used by the daily report.
    """
    if quantity <= 0:
        return 0
    lower = (quantity // 50) * 50
    return lower + 50 if quantity - lower > 10 else lower


def _is_lead_time_shortage(projected_coverage_days: Optional[float], lead_days: Optional[int]) -> bool:
    """Return whether supply runs out before an order placed today can arrive.

    The boundary is intentionally strict: 40 days of coverage against a
    40-day full lead time is due now, but is not a severe shortage.  Only a
    coverage value below the full lead time is urgent.
    """
    return bool(
        projected_coverage_days is not None
        and lead_days is not None
        and lead_days > 0
        and projected_coverage_days < lead_days
    )


def _purchase_category(category: Any) -> str:
    """Map WangDian's detailed category path to the order-form category.

    The order formula workbook only distinguishes wrist, knee, ankle, waist,
    and "other".  The source category is commonly a path such as
    ``护具/护腕``; all categories not explicitly named in the workbook belong
    to ``其他``.
    """
    value = str(category or "").strip()
    for name in ("护腕", "护膝", "护踝", "护腰"):
        if name in value:
            return name
    return "其他"


def _trend_purchase_multiplier(trend_coefficient: Optional[float]) -> float:
    """Return the workbook's purchase multiplier for a trend coefficient."""
    if trend_coefficient is None:
        return 1.0
    if trend_coefficient < 0.5:
        return 0.5
    if trend_coefficient < 0.8:
        return 0.6
    if trend_coefficient < 1.2:
        return 1.0
    if trend_coefficient < 1.8:
        return 1.2
    return 1.4


def _target_week_multiplier(production_days: Optional[int]) -> Optional[float]:
    """Return the workbook target quantity in multiples of weekly sales A.

    The workbook expresses the target as 2A+2A, 4A+3A, or 4A+4A.  The
    production-day bands select the corresponding target for every listed
    structure/category combination.
    """
    if production_days is None:
        return None
    if production_days <= 20:
        return 4.0  # 2A safety stock + 2A production stock
    if production_days <= 25:
        return 7.0  # 4A safety stock + 3A production stock
    return 8.0  # 4A safety stock + 4A production stock


class InventoryDatabase:
    def __init__(self, path: Path, *, read_only: bool = False) -> None:
        self.path = Path(path)
        self.read_only = read_only
        if not self.read_only:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.initialize()
        elif not self.path.exists():
            raise FileNotFoundError(f"SQLite database not found: {self.path}")

    def connect(self) -> sqlite3.Connection:
        if self.read_only:
            # URI mode=ro prevents the API process from creating tables,
            # running migrations, or changing the cloud database.
            database_uri = f"file:{self.path.resolve()}?mode=ro"
            connection = sqlite3.connect(database_uri, uri=True, timeout=30)
        else:
            connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        if not self.read_only:
            connection.execute("PRAGMA journal_mode = WAL")
        return connection

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(SCHEMA)
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(sync_runs)").fetchall()
            }
            if "sales_count" not in columns:
                connection.execute(
                    "ALTER TABLE sync_runs ADD COLUMN sales_count INTEGER NOT NULL DEFAULT 0"
                )
            if "return_count" not in columns:
                connection.execute(
                    "ALTER TABLE sync_runs ADD COLUMN return_count INTEGER NOT NULL DEFAULT 0"
                )
            if "cancellation_count" not in columns:
                connection.execute(
                    "ALTER TABLE sync_runs ADD COLUMN cancellation_count INTEGER NOT NULL DEFAULT 0"
                )
            product_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(products)").fetchall()
            }
            if "short_name" not in product_columns:
                connection.execute(
                    "ALTER TABLE products ADD COLUMN short_name TEXT NOT NULL DEFAULT ''"
                )
            product_metadata_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(products)").fetchall()
            }
            migrations = {
                "supplier_id": "ALTER TABLE products ADD COLUMN supplier_id TEXT NOT NULL DEFAULT ''",
                "supplier_no": "ALTER TABLE products ADD COLUMN supplier_no TEXT NOT NULL DEFAULT ''",
                "supplier_name": "ALTER TABLE products ADD COLUMN supplier_name TEXT NOT NULL DEFAULT ''",
                "supplier_updated_at": "ALTER TABLE products ADD COLUMN supplier_updated_at TEXT NOT NULL DEFAULT ''",
                "purchase_price": "ALTER TABLE products ADD COLUMN purchase_price REAL",
                "category": "ALTER TABLE products ADD COLUMN category TEXT NOT NULL DEFAULT ''",
                "product_structure": "ALTER TABLE products ADD COLUMN product_structure TEXT NOT NULL DEFAULT ''",
                "moq": "ALTER TABLE products ADD COLUMN moq REAL",
                "production_days": "ALTER TABLE products ADD COLUMN production_days INTEGER",
                "production_line": "ALTER TABLE products ADD COLUMN production_line TEXT NOT NULL DEFAULT ''",
                "production_capacity": "ALTER TABLE products ADD COLUMN production_capacity TEXT NOT NULL DEFAULT ''",
                "spec_remark": "ALTER TABLE products ADD COLUMN spec_remark TEXT NOT NULL DEFAULT ''",
                "goods_remark": "ALTER TABLE products ADD COLUMN goods_remark TEXT NOT NULL DEFAULT ''",
                "erp_price": "ALTER TABLE products ADD COLUMN erp_price REAL",
                "metadata_status": "ALTER TABLE products ADD COLUMN metadata_status TEXT NOT NULL DEFAULT '待补充'",
                "metadata_source": "ALTER TABLE products ADD COLUMN metadata_source TEXT NOT NULL DEFAULT ''",
                "metadata_updated_at": "ALTER TABLE products ADD COLUMN metadata_updated_at TEXT NOT NULL DEFAULT ''",
            }
            for name, statement in migrations.items():
                if name not in product_metadata_columns:
                    connection.execute(statement)
            # Backfill fields that are already present in previously captured
            # WangDian payloads. Goods-query payloads use spec remark directly
            # and prop1 for ERP price. Do not use the generic `remark` field as
            # a spec-remark fallback: it is the goods-level remark in goods_query.
            connection.execute(
                """
                UPDATE products
                SET spec_remark=COALESCE(NULLIF(spec_remark,''),
                    NULLIF(json_extract(raw_json,'$.spec_remark'),''), '')
                WHERE COALESCE(spec_remark,'')=''
                """
            )
            connection.execute(
                """
                UPDATE products
                SET goods_remark=COALESCE(NULLIF(goods_remark,''),
                    NULLIF(json_extract(raw_json,'$.goods_remark'),''), '')
                WHERE COALESCE(goods_remark,'')=''
                """
            )
            connection.execute(
                """
                UPDATE products
                SET erp_price=COALESCE(erp_price,
                    CASE
                        WHEN json_extract(raw_json,'$.erp_price') IS NOT NULL
                        THEN CAST(json_extract(raw_json,'$.erp_price') AS REAL)
                        WHEN json_extract(raw_json,'$.prop1') GLOB '-?[0-9]*.?[0-9]*'
                        THEN CAST(json_extract(raw_json,'$.prop1') AS REAL)
                    END)
                WHERE erp_price IS NULL
                """
            )
            connection.execute(
                "UPDATE products SET metadata_status='待补充' WHERE metadata_status=''"
            )
            inventory_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(inventory_current)").fetchall()
            }
            if "purchase_in_transit_num" not in inventory_columns:
                connection.execute(
                    "ALTER TABLE inventory_current ADD COLUMN purchase_in_transit_num REAL NOT NULL DEFAULT 0"
                )
            snapshot_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(inventory_snapshots)").fetchall()
            }
            if "purchase_in_transit_num" not in snapshot_columns:
                connection.execute(
                    "ALTER TABLE inventory_snapshots ADD COLUMN purchase_in_transit_num REAL NOT NULL DEFAULT 0"
                )
            clearance_snapshot_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(clearance_weekly_snapshots)").fetchall()
            }
            clearance_snapshot_migrations = {
                "purchase_price": "ALTER TABLE clearance_weekly_snapshots ADD COLUMN purchase_price REAL NOT NULL DEFAULT 0",
                "purchase_cost": "ALTER TABLE clearance_weekly_snapshots ADD COLUMN purchase_cost REAL NOT NULL DEFAULT 0",
            }
            for name, statement in clearance_snapshot_migrations.items():
                if name not in clearance_snapshot_columns:
                    connection.execute(statement)
            sales_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(sales_lines)").fetchall()
            }
            sales_migrations = {
                "shop_id": "ALTER TABLE sales_lines ADD COLUMN shop_id TEXT NOT NULL DEFAULT ''",
                "shop_no": "ALTER TABLE sales_lines ADD COLUMN shop_no TEXT NOT NULL DEFAULT ''",
                "shop_name": "ALTER TABLE sales_lines ADD COLUMN shop_name TEXT NOT NULL DEFAULT ''",
            }
            for name, statement in sales_migrations.items():
                if name not in sales_columns:
                    connection.execute(statement)
            warehouse_columns = {
                row["name"] for row in connection.execute("PRAGMA table_info(warehouse_master)").fetchall()
            }
            if "transfer_source_enabled" not in warehouse_columns:
                connection.execute(
                    "ALTER TABLE warehouse_master ADD COLUMN transfer_source_enabled INTEGER NOT NULL DEFAULT 0"
                )
            # Existing transfer-out history is the user's confirmed source-warehouse list.
            connection.execute(
                """
                UPDATE warehouse_master SET transfer_source_enabled=1
                WHERE warehouse_id IN (
                    SELECT DISTINCT warehouse_id FROM movements
                    WHERE movement_type=-2 AND out_num>0
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_sales_lines_shop_date ON sales_lines(shop_no, sale_date)"
            )
            disabled_placeholders = ",".join("?" for _ in DISABLED_WAREHOUSE_NAMES)
            connection.execute(
                f"UPDATE warehouse_master SET is_disabled=1, transfer_source_enabled=0 WHERE warehouse_name IN ({disabled_placeholders})",
                DISABLED_WAREHOUSE_NAMES,
            )
            # Return and defective warehouses are for return handling only. They
            # do not contribute sellable inventory, sales demand or transfers.
            connection.execute(
                "UPDATE warehouse_master SET transfer_source_enabled=0 WHERE role IN ('return','defective','virtual','clearance')"
            )
            for name, type_id in MOVEMENT_TYPES.items():
                connection.execute(
                    "UPDATE movements SET movement_type=? WHERE movement_name=?",
                    (type_id, name),
                )

    def is_empty(self) -> bool:
        with self.connect() as connection:
            row = connection.execute("SELECT COUNT(*) AS count FROM products").fetchone()
        return not row or row["count"] == 0

    def upsert_products(self, products: Iterable[Mapping[str, Any]]) -> int:
        now = datetime.now().isoformat(timespec="seconds")
        rows = []
        for item in products:
            sku_no = str(item.get("sku_no") or item.get("spec_no") or "").strip()
            if not sku_no:
                continue
            goods_remark = str(item.get("goods_remark") or "").strip()
            # `remark` is retained as a legacy goods-level input for callers
            # that have not been upgraded yet; it must never populate
            # spec_remark.
            legacy_goods_remark = str(item.get("remark") or "").strip()
            goods_remark = goods_remark or legacy_goods_remark
            remark = str(item.get("sku_remark") or goods_remark or "")
            spec_remark = str(
                item.get("spec_remark") or item.get("sku_remark") or ""
            ).strip()
            raw_erp_price = item.get("erp_price")
            if raw_erp_price in (None, ""):
                raw_erp_price = item.get("prop1")
            erp_price = to_float(raw_erp_price) if raw_erp_price not in (None, "") else None
            clearance_structure = "清仓款" if "清仓" in remark else ""
            product_structure = str(item.get("product_structure") or "").strip() or clearance_structure
            raw_production_days = item.get("production_days")
            production_days = None
            if raw_production_days not in (None, ""):
                digits = "".join(ch for ch in str(raw_production_days) if ch.isdigit())
                production_days = int(digits) if digits else None
            rows.append(
                (
                    sku_no,
                    str(item.get("goods_no") or item.get("spu_no") or ""),
                    str(item.get("goods_name") or item.get("spu_name") or ""),
                    str(item.get("short_name") or item.get("spu_short_name") or ""),
                    str(item.get("spec_name") or item.get("sku_name") or ""),
                    str(item.get("barcode") or ""),
                    str(item.get("unit_name") or item.get("unit") or ""),
                    str(item.get("provider_id") or item.get("supplier_id") or ""),
                    str(item.get("provider_no") or item.get("supplier_no") or ""),
                    str(item.get("provider_name") or item.get("supplier_name") or ""),
                    to_float(item.get("retail_price") or item.get("price")),
                    to_float(item.get("wholesale_price")),
                    (to_float(item.get("sku_default_purchase_price"))
                     if "sku_default_purchase_price" in item else None),
                    product_structure,
                    production_days,
                    str(item.get("production_line") or "").strip(),
                    str(item.get("production_capacity") or "").strip(),
                    spec_remark,
                    goods_remark,
                    erp_price,
                    now,
                    json.dumps(item, ensure_ascii=False, separators=(",", ":")),
                )
            )
        if not rows:
            return 0
        with self.connect() as connection:
            connection.executemany(
                """
                INSERT INTO products (
                    sku_no, goods_no, goods_name, short_name, spec_name, barcode, unit_name,
                    supplier_id, supplier_no, supplier_name,
                    retail_price, wholesale_price, purchase_price, product_structure,
                    production_days, production_line, production_capacity, spec_remark,
                    goods_remark, erp_price, updated_at, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(sku_no) DO UPDATE SET
                    goods_no=COALESCE(NULLIF(excluded.goods_no, ''), products.goods_no),
                    goods_name=COALESCE(NULLIF(excluded.goods_name, ''), products.goods_name),
                    short_name=COALESCE(NULLIF(excluded.short_name, ''), products.short_name),
                    spec_name=COALESCE(NULLIF(excluded.spec_name, ''), products.spec_name),
                    barcode=COALESCE(NULLIF(excluded.barcode, ''), products.barcode),
                    unit_name=COALESCE(NULLIF(excluded.unit_name, ''), products.unit_name),
                    supplier_id=COALESCE(NULLIF(excluded.supplier_id, ''), products.supplier_id),
                    supplier_no=COALESCE(NULLIF(excluded.supplier_no, ''), products.supplier_no),
                    supplier_name=COALESCE(NULLIF(excluded.supplier_name, ''), products.supplier_name),
                    supplier_updated_at=CASE WHEN excluded.supplier_name<>'' THEN excluded.updated_at ELSE products.supplier_updated_at END,
                    retail_price=CASE WHEN excluded.retail_price > 0 THEN excluded.retail_price ELSE products.retail_price END,
                    wholesale_price=CASE WHEN excluded.wholesale_price > 0 THEN excluded.wholesale_price ELSE products.wholesale_price END,
                    purchase_price=CASE WHEN excluded.purchase_price IS NULL THEN products.purchase_price ELSE excluded.purchase_price END,
                    product_structure=CASE WHEN excluded.product_structure='清仓款' THEN '清仓款' WHEN excluded.product_structure<>'' THEN excluded.product_structure ELSE products.product_structure END,
                    production_days=CASE WHEN excluded.production_days IS NULL THEN products.production_days ELSE excluded.production_days END,
                    production_line=COALESCE(NULLIF(excluded.production_line, ''), products.production_line),
                    production_capacity=COALESCE(NULLIF(excluded.production_capacity, ''), products.production_capacity),
                    -- Only a goods_query upsert (which carries the explicit
                    -- goods_remark key in raw_json) may clear/replace an
                    -- existing spec remark. Sales, returns and inventory
                    -- payloads do not contain this key and must preserve the
                    -- product master value.
                    spec_remark=CASE
                        WHEN json_extract(excluded.raw_json, '$.goods_remark') IS NOT NULL
                        THEN excluded.spec_remark
                        ELSE products.spec_remark
                    END,
                    goods_remark=CASE
                        WHEN json_extract(excluded.raw_json, '$.goods_remark') IS NOT NULL
                        THEN excluded.goods_remark
                        ELSE products.goods_remark
                    END,
                    erp_price=CASE WHEN excluded.erp_price IS NULL THEN products.erp_price ELSE excluded.erp_price END,
                    updated_at=excluded.updated_at,
                    raw_json=excluded.raw_json
                """,
                rows,
            )
        return len(rows)

    def upsert_product_suppliers(self, products: Iterable[Mapping[str, Any]]) -> Dict[str, int]:
        """Write supplier information returned by the WangDian goods master API."""
        now = datetime.now().isoformat(timespec="seconds")
        rows = []
        for item in products:
            sku_no = str(item.get("sku_no") or item.get("spec_no") or "").strip()
            if not sku_no:
                continue
            rows.append((
                str(item.get("provider_id") or item.get("supplier_id") or "").strip(),
                str(item.get("provider_no") or item.get("supplier_no") or "").strip(),
                str(item.get("provider_name") or item.get("supplier_name") or "").strip(),
                now,
                sku_no,
            ))
        if not rows:
            return {"updated": 0, "matched": 0, "with_supplier": 0}
        with self.connect() as connection:
            sku_numbers = list({row[-1] for row in rows})
            placeholders = ",".join("?" for _ in sku_numbers)
            matched = connection.execute(
                f"SELECT COUNT(*) FROM products WHERE sku_no IN ({placeholders})",
                sku_numbers,
            ).fetchone()[0]
            connection.executemany(
                """
                UPDATE products SET
                    supplier_id=?, supplier_no=?, supplier_name=?, supplier_updated_at=?
                WHERE sku_no=?
                """,
                rows,
            )
        return {
            "updated": int(matched),
            "matched": int(matched),
            "with_supplier": sum(1 for row in rows if row[2]),
        }

    def upsert_product_metadata(
        self,
        metadata: Iterable[Mapping[str, Any]],
        *,
        source: str = "",
    ) -> Dict[str, int]:
        """Apply curated product planning fields without overwriting ERP facts."""
        now = datetime.now().isoformat(timespec="seconds")
        rows = []
        for item in metadata:
            sku_no = str(item.get("sku_no") or item.get("商家编码") or "").strip()
            if not sku_no:
                continue
            category = str(item.get("category") or item.get("品类") or "").strip()
            structure = str(
                item.get("product_structure") or item.get("四大结构") or ""
            ).strip()
            raw_moq = item.get("moq", item.get("起订量"))
            moq = None
            if raw_moq not in (None, "") and str(raw_moq).strip() != "无":
                moq = to_float(raw_moq)
            raw_days = item.get("production_days", item.get("生产周期"))
            production_days = None
            if raw_days not in (None, ""):
                text = str(raw_days).strip()
                digits = "".join(ch for ch in text if ch.isdigit())
                production_days = int(digits) if digits else None
            # The source explicitly distinguishes “无” MOQ from missing data.
            status = str(item.get("metadata_status") or "已配置").strip()
            rows.append(
                (
                    category,
                    structure,
                    moq,
                    production_days,
                    status,
                    source,
                    now,
                    sku_no,
                )
            )
        if not rows:
            return {"updated": 0, "matched": 0, "unmatched": 0}
        with self.connect() as connection:
            placeholders = ",".join("?" for _ in rows)
            matched = connection.execute(
                f"SELECT COUNT(*) FROM products WHERE sku_no IN ({placeholders})",
                [row[-1] for row in rows],
            ).fetchone()[0]
            connection.executemany(
                """
                UPDATE products SET
                    category=?, product_structure=?, moq=?, production_days=?,
                    metadata_status=?, metadata_source=?, metadata_updated_at=?
                WHERE sku_no=?
                """,
                rows,
            )
        return {
            "updated": int(matched),
            "matched": int(matched),
            "unmatched": len(rows) - int(matched),
        }

    def mark_clearance_products_from_remarks(self) -> int:
        """Set the product structure from the latest WangDian SKU remark."""
        candidates = []
        with self.connect() as connection:
            rows = connection.execute("SELECT sku_no, raw_json FROM products").fetchall()
            for row in rows:
                try:
                    raw = json.loads(row["raw_json"])
                except (TypeError, json.JSONDecodeError):
                    continue
                if not isinstance(raw, dict):
                    continue
                remark = str(raw.get("sku_remark") or raw.get("remark") or "")
                if "清仓" in remark:
                    candidates.append((row["sku_no"],))
            if not candidates:
                return 0
            before = connection.total_changes
            connection.executemany(
                """
                UPDATE products SET product_structure='清仓款'
                WHERE sku_no=? AND product_structure<>'清仓款'
                """,
                candidates,
            )
            return connection.total_changes - before

    def upsert_movements(self, movements: Iterable[Mapping[str, Any]]) -> int:
        rows = []
        legacy_keys_to_remove = set()
        for item in movements:
            sku_no = str(item.get("sku_no") or item.get("spec_no") or "").strip()
            if not sku_no:
                continue
            event_time = str(item.get("create_date") or item.get("modified") or "")
            movement_date = event_time[:10]
            if len(movement_date) != 10:
                continue
            in_num = to_float(item.get("in_num"))
            out_num = to_float(item.get("out_num"))
            type_id = movement_type(item)
            source_id = str(item.get("src_id") or "")
            detail_id = str(item.get("src_detail_id") or item.get("rec_id") or "")
            src_order_no = str(item.get("src_order_no") or "")
            key = movement_key(item)
            if item.get("_api_duplicate_index") not in (None, ""):
                base_item = dict(item)
                base_item.pop("_api_duplicate_index", None)
                legacy_keys_to_remove.add(movement_key(base_item))
            rows.append(
                (
                    key,
                    movement_date,
                    event_time,
                    sku_no,
                    str(item.get("warehouse_id") or ""),
                    str(item.get("warehouse_no") or ""),
                    str(item.get("warehouse_name") or ""),
                    type_id,
                    str(item.get("in_out_type") or ""),
                    in_num,
                    out_num,
                    in_num - out_num,
                    src_order_no,
                    source_id,
                    detail_id,
                    "{}",
                )
            )
        if not rows:
            return 0
        with self.connect() as connection:
            if legacy_keys_to_remove:
                connection.executemany(
                    "DELETE FROM movements WHERE movement_key=?",
                    [(key,) for key in legacy_keys_to_remove],
                )
            before = connection.total_changes
            connection.executemany(
                """
                INSERT INTO movements VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(movement_key) DO UPDATE SET
                    movement_date=excluded.movement_date,
                    event_time=excluded.event_time,
                    in_num=excluded.in_num,
                    out_num=excluded.out_num,
                    quantity=excluded.quantity,
                    raw_json=excluded.raw_json
                """,
                rows,
            )
            changed = connection.total_changes - before
        return changed

    def upsert_warehouses(self, warehouses: Iterable[Mapping[str, Any]]) -> int:
        rows = []
        for item in warehouses:
            warehouse_id = str(item.get("warehouse_id") or "").strip()
            if not warehouse_id:
                continue
            name = str(item.get("name") or item.get("warehouse_name") or "").strip()
            if "残次" in name or "次品" in name:
                role = "defective"
            elif "退货" in name:
                role = "return"
            elif "虚拟" in name:
                role = "virtual"
            elif "滞销" in name or "销毁" in name:
                role = "clearance"
            else:
                role = "sales"
            rows.append(
                (
                    warehouse_id,
                    str(item.get("warehouse_no") or ""),
                    name,
                    int(to_float(item.get("warehouse_type"))),
                    int(to_float(item.get("is_disabled"))),
                    role,
                    int(to_float(item.get("transfer_source_enabled"))),
                    str(item.get("modified") or ""),
                    json.dumps(item, ensure_ascii=False, separators=(",", ":")),
                )
            )
        if not rows:
            return 0
        with self.connect() as connection:
            connection.executemany(
                """
                INSERT INTO warehouse_master (
                    warehouse_id,warehouse_no,warehouse_name,warehouse_type,is_disabled,role,
                    transfer_source_enabled,modified,raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(warehouse_id) DO UPDATE SET
                    warehouse_no=excluded.warehouse_no,
                    warehouse_name=excluded.warehouse_name,
                    warehouse_type=excluded.warehouse_type,
                    is_disabled=excluded.is_disabled,
                    role=CASE
                        WHEN warehouse_master.role IN ('sales','return','defective','virtual','clearance')
                        THEN excluded.role ELSE warehouse_master.role END,
                    transfer_source_enabled=CASE
                        WHEN excluded.transfer_source_enabled=1 THEN 1
                        ELSE warehouse_master.transfer_source_enabled END,
                    modified=excluded.modified,
                    raw_json=excluded.raw_json
                """,
                rows,
            )
            disabled_placeholders = ",".join("?" for _ in DISABLED_WAREHOUSE_NAMES)
            connection.execute(
                f"UPDATE warehouse_master SET is_disabled=1, transfer_source_enabled=0 WHERE warehouse_name IN ({disabled_placeholders})",
                DISABLED_WAREHOUSE_NAMES,
            )
            connection.execute(
                "UPDATE warehouse_master SET transfer_source_enabled=0 WHERE role IN ('return','defective','virtual','clearance')"
            )
            connection.execute(
                """
                UPDATE inventory_current
                SET warehouse_no=COALESCE(NULLIF(warehouse_no,''),(
                        SELECT wm.warehouse_no FROM warehouse_master wm
                        WHERE wm.warehouse_id=inventory_current.warehouse_id)),
                    warehouse_name=COALESCE(NULLIF(warehouse_name,''),(
                        SELECT wm.warehouse_name FROM warehouse_master wm
                        WHERE wm.warehouse_id=inventory_current.warehouse_id))
                WHERE warehouse_id IN (SELECT warehouse_id FROM warehouse_master)
                """
            )
        return len(rows)

    def warehouse_lookup(self) -> Dict[str, Dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute("SELECT * FROM warehouse_master").fetchall()
        return {str(row["warehouse_id"]): dict(row) for row in rows}

    def upsert_sales_orders(self, orders: Iterable[Mapping[str, Any]]) -> int:
        rows = []
        products = []
        for order in orders:
            consign_time = str(order.get("consign_time") or order.get("modified") or "")
            sale_date = consign_time[:10]
            if len(sale_date) != 10:
                continue
            stockout_id = str(order.get("stockout_id") or "")
            for detail in order.get("details_list") or []:
                if not isinstance(detail, Mapping):
                    continue
                sku_no = str(detail.get("spec_no") or detail.get("sku_no") or "").strip()
                if not sku_no:
                    continue
                detail_id = str(detail.get("rec_id") or "")
                source_detail_id = str(
                    detail.get("src_order_detail_id") or detail_id
                )
                sale_key = "|".join((stockout_id, detail_id or source_detail_id, sku_no))
                merged = dict(order)
                merged.pop("details_list", None)
                merged["detail"] = dict(detail)
                rows.append(
                    (
                        sale_key,
                        sale_date,
                        consign_time,
                        sku_no,
                        str(order.get("warehouse_id") or ""),
                        str(order.get("warehouse_no") or ""),
                        str(order.get("warehouse_name") or ""),
                        str(order.get("shop_id") or ""),
                        str(order.get("shop_no") or ""),
                        str(order.get("shop_name") or ""),
                        stockout_id,
                        detail_id,
                        source_detail_id,
                        str(order.get("src_order_no") or ""),
                        str(order.get("order_no") or ""),
                        to_float(detail.get("actual_num")) or to_float(detail.get("num")),
                        to_float(detail.get("paid")),
                        to_float(detail.get("share_amount")),
                        to_float(detail.get("retail_price")),
                        to_float(detail.get("sell_price") or detail.get("price")),
                        to_float(detail.get("cost_price") or detail.get("goods_cost")),
                        int(to_float(order.get("status"))),
                        str(detail.get("modified") or order.get("modified") or ""),
                        json.dumps(merged, ensure_ascii=False, separators=(",", ":")),
                    )
                )
                products.append(detail)
        if not rows:
            return 0
        with self.connect() as connection:
            connection.executemany(
                """
                INSERT INTO sales_lines (
                    sale_key,sale_date,consign_time,sku_no,warehouse_id,warehouse_no,warehouse_name,
                    shop_id,shop_no,shop_name,stockout_id,detail_id,source_detail_id,src_order_no,order_no,
                    quantity,paid_amount,share_amount,retail_price,sell_price,cost_price,status,modified,raw_json
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                ON CONFLICT(sale_key) DO UPDATE SET
                    sale_date=excluded.sale_date,
                    consign_time=excluded.consign_time,
                    warehouse_id=excluded.warehouse_id,
                    warehouse_no=excluded.warehouse_no,
                    warehouse_name=excluded.warehouse_name,
                    shop_id=excluded.shop_id,
                    shop_no=excluded.shop_no,
                    shop_name=excluded.shop_name,
                    quantity=excluded.quantity,
                    paid_amount=excluded.paid_amount,
                    share_amount=excluded.share_amount,
                    retail_price=excluded.retail_price,
                    sell_price=excluded.sell_price,
                    cost_price=excluded.cost_price,
                    status=excluded.status,
                    modified=excluded.modified,
                    raw_json=excluded.raw_json
                """,
                rows,
            )
        self.upsert_products(products)
        return len(rows)

    def upsert_return_orders(self, orders: Iterable[Mapping[str, Any]]) -> int:
        rows = []
        products = []
        for order in orders:
            stockin_time = str(
                order.get("stockin_time") or order.get("check_time") or order.get("modified") or ""
            )
            return_date = stockin_time[:10]
            if len(return_date) != 10:
                continue
            stockin_id = str(order.get("stockin_id") or "")
            for detail in order.get("details_list") or []:
                if not isinstance(detail, Mapping):
                    continue
                sku_no = str(detail.get("spec_no") or detail.get("sku_no") or "").strip()
                if not sku_no:
                    continue
                detail_id = str(detail.get("rec_id") or "")
                source_detail_id = str(
                    detail.get("src_order_detail_id") or detail_id
                )
                return_key = "|".join((stockin_id, detail_id or source_detail_id, sku_no))
                merged = dict(order)
                merged.pop("details_list", None)
                merged["detail"] = dict(detail)
                rows.append(
                    (
                        return_key,
                        return_date,
                        stockin_time,
                        sku_no,
                        str(order.get("warehouse_id") or ""),
                        str(order.get("warehouse_no") or ""),
                        str(order.get("warehouse_name") or ""),
                        stockin_id,
                        detail_id,
                        source_detail_id,
                        str(order.get("src_order_no") or order.get("trade_no") or ""),
                        str(order.get("order_no") or ""),
                        to_float(detail.get("num")),
                        to_float(detail.get("actual_refund_amount")),
                        to_float(detail.get("src_price")),
                        to_float(detail.get("cost_price") or detail.get("stockin_price")),
                        int(to_float(order.get("status"))),
                        str(detail.get("modified") or order.get("modified") or ""),
                        json.dumps(merged, ensure_ascii=False, separators=(",", ":")),
                    )
                )
                products.append(detail)
        if not rows:
            return 0
        with self.connect() as connection:
            connection.executemany(
                """
                INSERT INTO return_lines VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                ON CONFLICT(return_key) DO UPDATE SET
                    return_date=excluded.return_date,
                    stockin_time=excluded.stockin_time,
                    quantity=excluded.quantity,
                    refund_amount=excluded.refund_amount,
                    source_price=excluded.source_price,
                    cost_price=excluded.cost_price,
                    status=excluded.status,
                    modified=excluded.modified,
                    raw_json=excluded.raw_json
                """,
                rows,
            )
        self.upsert_products(products)
        return len(rows)

    def update_sales_statuses(self, orders: Iterable[Mapping[str, Any]]) -> int:
        rows = []
        for order in orders:
            stockout_id = str(order.get("stockout_id") or "")
            src_order_no = str(order.get("src_order_no") or order.get("order_no") or "")
            if not stockout_id and not src_order_no:
                continue
            rows.append(
                (
                    int(to_float(order.get("status"))),
                    str(order.get("modified") or ""),
                    stockout_id,
                    src_order_no,
                )
            )
        if not rows:
            return 0
        with self.connect() as connection:
            before = connection.total_changes
            connection.executemany(
                "UPDATE sales_lines SET status=?, modified=? WHERE stockout_id=? OR src_order_no=?",
                rows,
            )
            return connection.total_changes - before

    def upsert_inventory(self, stocks: Iterable[Mapping[str, Any]], snapshot_date: str) -> int:
        now = datetime.now().isoformat(timespec="seconds")
        rows = []
        snapshots = []
        for item in stocks:
            sku_no = str(item.get("spec_no") or item.get("sku_no") or "").strip()
            if not sku_no:
                continue
            warehouse_id = str(item.get("warehouse_id") or item.get("warehouse_no") or "")
            stock_num = inventory_number(item.get("stock_num"))
            available_num = inventory_number(item.get("available_num"))
            cost_price = to_float(item.get("cost_price"))
            avg_cost_price = to_float(item.get("avg_cost_price"))
            purchase_in_transit_num = max(0.0, inventory_number(item.get("purchase_in_transit_num")))
            rows.append(
                (
                    sku_no,
                    warehouse_id,
                    str(item.get("warehouse_no") or ""),
                    str(item.get("warehouse_name") or ""),
                    stock_num,
                    available_num,
                    cost_price,
                    avg_cost_price,
                    purchase_in_transit_num,
                    str(item.get("modified") or ""),
                    now,
                    json.dumps(item, ensure_ascii=False, separators=(",", ":")),
                )
            )
            snapshots.append(
                (snapshot_date, sku_no, warehouse_id, stock_num, available_num,
                 avg_cost_price or cost_price, purchase_in_transit_num)
            )
        if not rows:
            return 0
        with self.connect() as connection:
            connection.executemany(
                """
                INSERT INTO inventory_current (
                    sku_no, warehouse_id, warehouse_no, warehouse_name, stock_num,
                    available_num, cost_price, avg_cost_price, purchase_in_transit_num,
                    modified, synced_at, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(sku_no, warehouse_id) DO UPDATE SET
                    warehouse_no=excluded.warehouse_no,
                    warehouse_name=excluded.warehouse_name,
                    stock_num=excluded.stock_num,
                    available_num=excluded.available_num,
                    cost_price=excluded.cost_price,
                    avg_cost_price=excluded.avg_cost_price,
                    purchase_in_transit_num=excluded.purchase_in_transit_num,
                    modified=excluded.modified,
                    synced_at=excluded.synced_at,
                    raw_json=excluded.raw_json
                """,
                rows,
            )
            connection.executemany(
                """
                INSERT INTO inventory_snapshots (
                    snapshot_date, sku_no, warehouse_id, stock_num, available_num,
                    cost_price, purchase_in_transit_num
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(snapshot_date, sku_no, warehouse_id) DO UPDATE SET
                    stock_num=excluded.stock_num,
                    available_num=excluded.available_num,
                    cost_price=excluded.cost_price,
                    purchase_in_transit_num=excluded.purchase_in_transit_num
                """,
                snapshots,
            )
        return len(rows)

    def replace_inventory(self, stocks: Iterable[Mapping[str, Any]], snapshot_date: str) -> int:
        source_records = list(stocks)
        warehouse_lookup = self.warehouse_lookup()
        aggregated: Dict[tuple[str, str], Dict[str, Any]] = {}
        for item in source_records:
            sku_no = str(item.get("spec_no") or item.get("sku_no") or "").strip()
            if not sku_no:
                continue
            warehouse_id = str(item.get("warehouse_id") or item.get("warehouse_no") or "")
            normalized_item = dict(item)
            warehouse = warehouse_lookup.get(warehouse_id, {})
            normalized_item["warehouse_no"] = (
                normalized_item.get("warehouse_no") or warehouse.get("warehouse_no") or ""
            )
            normalized_item["warehouse_name"] = (
                normalized_item.get("warehouse_name") or warehouse.get("warehouse_name") or ""
            )
            item = normalized_item
            key = (sku_no, warehouse_id)
            if key not in aggregated:
                merged = dict(item)
                merged["inventory_parts"] = [dict(item)]
                merged["good_stock_num"] = (
                    inventory_number(item.get("stock_num")) if int(to_float(item.get("defect"))) != 1 else 0
                )
                merged["defect_stock_num"] = (
                    inventory_number(item.get("stock_num")) if int(to_float(item.get("defect"))) == 1 else 0
                )
                aggregated[key] = merged
                continue
            merged = aggregated[key]
            merged["inventory_parts"].append(dict(item))
            merged["stock_num"] = inventory_number(merged.get("stock_num")) + inventory_number(item.get("stock_num"))
            merged["available_num"] = inventory_number(merged.get("available_num")) + inventory_number(item.get("available_num"))
            if int(to_float(item.get("defect"))) == 1:
                merged["defect_stock_num"] += inventory_number(item.get("stock_num"))
            else:
                merged["good_stock_num"] += inventory_number(item.get("stock_num"))
            if not to_float(merged.get("avg_cost_price")):
                merged["avg_cost_price"] = item.get("avg_cost_price")
            if not to_float(merged.get("cost_price")):
                merged["cost_price"] = item.get("cost_price")
            # purchase_in_transit_num is a warehouse/SKU level total in the
            # stock query. Good/defective rows can repeat it, so retain the
            # largest value rather than double counting it during aggregation.
            merged["purchase_in_transit_num"] = max(
                inventory_number(merged.get("purchase_in_transit_num")),
                inventory_number(item.get("purchase_in_transit_num")),
            )
        records = list(aggregated.values())
        now = datetime.now().isoformat(timespec="seconds")
        current_rows = []
        snapshot_rows = []
        for item in records:
            sku_no = str(item.get("spec_no") or item.get("sku_no") or "").strip()
            if not sku_no:
                continue
            warehouse_id = str(item.get("warehouse_id") or item.get("warehouse_no") or "")
            stock_num = inventory_number(item.get("stock_num"))
            available_num = inventory_number(item.get("available_num"))
            cost_price = to_float(item.get("cost_price"))
            avg_cost_price = to_float(item.get("avg_cost_price"))
            purchase_in_transit_num = max(0.0, inventory_number(item.get("purchase_in_transit_num")))
            current_rows.append(
                (
                    sku_no,
                    warehouse_id,
                    str(item.get("warehouse_no") or ""),
                    str(item.get("warehouse_name") or ""),
                    stock_num,
                    available_num,
                    cost_price,
                    avg_cost_price,
                    purchase_in_transit_num,
                    str(item.get("modified") or ""),
                    now,
                    json.dumps(item, ensure_ascii=False, separators=(",", ":")),
                )
            )
            snapshot_rows.append(
                (snapshot_date, sku_no, warehouse_id, stock_num, available_num,
                 avg_cost_price or cost_price, purchase_in_transit_num)
            )
        with self.connect() as connection:
            connection.execute("DELETE FROM inventory_current")
            connection.execute(
                "DELETE FROM inventory_snapshots WHERE snapshot_date=?", (snapshot_date,)
            )
            connection.executemany(
                """
                INSERT INTO inventory_current (
                    sku_no, warehouse_id, warehouse_no, warehouse_name, stock_num,
                    available_num, cost_price, avg_cost_price, purchase_in_transit_num,
                    modified, synced_at, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                current_rows,
            )
            connection.executemany(
                """
                INSERT INTO inventory_snapshots (
                    snapshot_date, sku_no, warehouse_id, stock_num, available_num,
                    cost_price, purchase_in_transit_num
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                snapshot_rows,
            )
        self.upsert_products(records)
        return len(current_rows)

    def product_skus(self) -> List[str]:
        with self.connect() as connection:
            rows = connection.execute("SELECT sku_no FROM products ORDER BY sku_no").fetchall()
        return [row["sku_no"] for row in rows]

    def movement_count(self, movement_date: str) -> int:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) count FROM movements WHERE movement_date=?",
                (movement_date,),
            ).fetchone()
        return int(row["count"] if row else 0)

    def start_sync(self, sync_date: str) -> int:
        now = datetime.now().isoformat(timespec="seconds")
        with self.connect() as connection:
            cursor = connection.execute(
                "INSERT INTO sync_runs(sync_date, status, started_at) VALUES (?, 'running', ?)",
                (sync_date, now),
            )
            return int(cursor.lastrowid)

    def finish_sync(
        self,
        run_id: int,
        *,
        status: str,
        movement_count: int = 0,
        inventory_count: int = 0,
        sales_count: int = 0,
        return_count: int = 0,
        cancellation_count: int = 0,
        error_message: str = "",
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE sync_runs SET status=?, movement_count=?, inventory_count=?,
                    sales_count=?, return_count=?, cancellation_count=?,
                    finished_at=?, error_message=? WHERE id=?
                """,
                (
                    status,
                    movement_count,
                    inventory_count,
                    sales_count,
                    return_count,
                    cancellation_count,
                    datetime.now().isoformat(timespec="seconds"),
                    error_message,
                    run_id,
                ),
            )

    def last_sync(self) -> Optional[Dict[str, Any]]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM sync_runs ORDER BY id DESC LIMIT 1"
            ).fetchone()
        return dict(row) if row else None

    def warehouses(self) -> List[Dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT i.warehouse_id, MAX(i.warehouse_no) warehouse_no,
                       MAX(i.warehouse_name) warehouse_name,
                       COUNT(DISTINCT i.sku_no) sku_count,
                       SUM(i.stock_num) stock_num,
                       SUM(i.available_num) available_num,
                       SUM(i.purchase_in_transit_num) purchase_in_transit_num
                FROM inventory_current i
                LEFT JOIN products p ON p.sku_no=i.sku_no
                LEFT JOIN warehouse_master wm ON wm.warehouse_id=i.warehouse_id
                WHERE p.goods_name NOT LIKE '%运费%'
                  AND p.goods_name NOT LIKE '%寄付%'
                  AND p.goods_name NOT LIKE '%赠品%'
                  AND p.goods_name NOT LIKE '%赠送%'
                  AND p.goods_name NOT LIKE '%不发货%'
                  AND p.goods_name NOT LIKE '%差价%'
                  AND COALESCE(wm.is_disabled,0)=0
                  AND COALESCE(wm.role,'sales')='sales'
                GROUP BY i.warehouse_id ORDER BY warehouse_name
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def record_clearance_weekly_snapshot(self, snapshot_date: str) -> int:
        """Freeze saleable clearance inventory and its default purchase price weekly."""
        snapshot_day = date.fromisoformat(snapshot_date)
        snapshot_week = snapshot_day.strftime("%G-W%V")
        recorded_at = datetime.now().isoformat(timespec="seconds")
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT i.sku_no, i.warehouse_id, i.stock_num, i.available_num,
                       COALESCE(p.purchase_price,0) purchase_price
                FROM inventory_current i
                JOIN products p ON p.sku_no=i.sku_no
                LEFT JOIN warehouse_master wm ON wm.warehouse_id=i.warehouse_id
                WHERE p.product_structure='清仓款'
                  AND COALESCE(wm.is_disabled,0)=0
                  AND COALESCE(wm.role,'sales')='sales'
                """
            ).fetchall()
            values = [
                (
                    snapshot_week,
                    snapshot_date,
                    row["sku_no"],
                    row["warehouse_id"],
                    row["stock_num"],
                    row["available_num"],
                    0,
                    0,
                    row["purchase_price"],
                    row["stock_num"] * row["purchase_price"],
                    recorded_at,
                )
                for row in rows
            ]
            if values:
                connection.executemany(
                    """
                    INSERT INTO clearance_weekly_snapshots(
                        snapshot_week,snapshot_date,sku_no,warehouse_id,stock_num,
                        available_num,unit_cost,stock_cost,purchase_price,purchase_cost,recorded_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(snapshot_week,sku_no,warehouse_id) DO UPDATE SET
                        snapshot_date=excluded.snapshot_date,
                        stock_num=excluded.stock_num,
                        available_num=excluded.available_num,
                        purchase_price=excluded.purchase_price,
                        purchase_cost=excluded.purchase_cost,
                        recorded_at=excluded.recorded_at
                    """,
                    values,
                )
        return len(values)

    def clearance_summary(
        self,
        *,
        search: str = "",
        warehouse_id: str = "",
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Return current saleable clearance stock at the goods-master purchase-price basis."""
        filters = [
            "p.product_structure='清仓款'",
            "COALESCE(wm.is_disabled,0)=0",
            "COALESCE(wm.role,'sales')='sales'",
        ]
        params: List[Any] = []
        if warehouse_id:
            filters.append("i.warehouse_id=?")
            params.append(warehouse_id)
        if search:
            filters.append(
                "(p.sku_no LIKE ? OR p.goods_no LIKE ? OR p.goods_name LIKE ? "
                "OR p.short_name LIKE ? OR p.spec_name LIKE ? OR p.barcode LIKE ?)"
            )
            params.extend([f"%{search}%"] * 6)
        where = " AND ".join(filters)
        with self.connect() as connection:
            summary = connection.execute(
                f"""
                SELECT COUNT(*) row_count, COUNT(DISTINCT i.sku_no) sku_count,
                       COUNT(DISTINCT i.warehouse_id) warehouse_count,
                       COALESCE(SUM(i.stock_num),0) stock_num,
                       COALESCE(SUM(i.available_num),0) available_num,
                       COALESCE(SUM(i.stock_num * COALESCE(p.purchase_price,0)),0) purchase_cost,
                       COALESCE(SUM(CASE WHEN i.stock_num>0 AND COALESCE(p.purchase_price,0)<=0 THEN 1 ELSE 0 END),0) missing_purchase_price_count,
                       MAX(i.synced_at) updated_at
                FROM inventory_current i
                JOIN products p ON p.sku_no=i.sku_no
                LEFT JOIN warehouse_master wm ON wm.warehouse_id=i.warehouse_id
                WHERE {where}
                """,
                params,
            ).fetchone()
            latest_week = connection.execute(
                """
                SELECT snapshot_week,snapshot_date,recorded_at,
                       COUNT(*) row_count,COUNT(DISTINCT sku_no) sku_count,
                       COALESCE(SUM(stock_num),0) stock_num,
                       COALESCE(SUM(available_num),0) available_num,
                       COALESCE(SUM(purchase_cost),0) purchase_cost
                FROM clearance_weekly_snapshots
                GROUP BY snapshot_week
                ORDER BY snapshot_date DESC,recorded_at DESC LIMIT 1
                """
            ).fetchone()
            rows = connection.execute(
                f"""
                SELECT i.sku_no,i.warehouse_id,i.warehouse_no,
                       COALESCE(NULLIF(i.warehouse_name,''),wm.warehouse_name,i.warehouse_no,'仓库 ' || i.warehouse_id) warehouse_name,
                       p.goods_no,p.goods_name,p.short_name,p.spec_name,p.category,p.supplier_name,
                       i.stock_num,i.available_num,
                       COALESCE(p.purchase_price,0) purchase_price,
                       i.stock_num * COALESCE(p.purchase_price,0) purchase_cost,
                       i.synced_at
                FROM inventory_current i
                JOIN products p ON p.sku_no=i.sku_no
                LEFT JOIN warehouse_master wm ON wm.warehouse_id=i.warehouse_id
                WHERE {where}
                ORDER BY purchase_cost DESC, i.stock_num DESC, p.short_name, i.sku_no
                LIMIT ? OFFSET ?
                """,
                params + [limit, offset],
            ).fetchall()
        return {
            "summary": dict(summary) if summary else {},
            "latest_weekly_snapshot": dict(latest_week) if latest_week else None,
            "items": [dict(row) for row in rows],
            "pagination": {
                "total": int(summary["row_count"] if summary else 0),
                "limit": limit,
                "offset": offset,
            },
        }

    def dashboard(
        self,
        start_date: str,
        end_date: str,
        *,
        search: str = "",
        warehouse_id: str = "",
        stock_status: str = "",
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        movement_where = ["m.movement_date BETWEEN ? AND ?"]
        movement_params: List[Any] = [start_date, end_date]
        sales_where = ["s.sale_date BETWEEN ? AND ?", "s.status >= 95"]
        sales_params: List[Any] = [start_date, end_date]
        return_where = ["r.return_date BETWEEN ? AND ?"]
        return_params: List[Any] = [start_date, end_date]
        product_is_physical = (
            "goods_name NOT LIKE '%运费%' AND goods_name NOT LIKE '%寄付%' "
            "AND goods_name NOT LIKE '%赠品%' AND goods_name NOT LIKE '%赠送%' "
            "AND goods_name NOT LIKE '%不发货%' AND goods_name NOT LIKE '%差价%'"
        )
        active_sales_warehouse_filter = "NOT EXISTS (SELECT 1 FROM warehouse_master wm WHERE wm.warehouse_id={alias}.warehouse_id AND (wm.is_disabled=1 OR wm.role<>'sales'))"
        active_return_warehouse_filter = "NOT EXISTS (SELECT 1 FROM warehouse_master wm WHERE wm.warehouse_id={alias}.warehouse_id AND wm.is_disabled=1)"
        # Sales and purchase movements belong to sales warehouses, but a
        # customer return is normally received in a dedicated return/defective
        # warehouse. Include only movement type 3 from those active warehouses.
        movement_warehouse_filter = (
            "NOT EXISTS (SELECT 1 FROM warehouse_master wm "
            "WHERE wm.warehouse_id={alias}.warehouse_id "
            "AND (wm.is_disabled=1 OR (wm.role<>'sales' AND {alias}.movement_type<>3)))"
        )
        movement_where.extend([
            f"m.sku_no IN (SELECT sku_no FROM products WHERE {product_is_physical})",
            movement_warehouse_filter.format(alias="m"),
        ])
        sales_where.extend([f"s.sku_no IN (SELECT sku_no FROM products WHERE {product_is_physical})", active_sales_warehouse_filter.format(alias="s")])
        return_where.extend([f"r.sku_no IN (SELECT sku_no FROM products WHERE {product_is_physical})", active_return_warehouse_filter.format(alias="r")])
        inventory_where: List[str] = [f"sku_no IN (SELECT sku_no FROM products WHERE {product_is_physical})", active_sales_warehouse_filter.format(alias="inventory_current")]
        inventory_params: List[Any] = []
        if warehouse_id:
            movement_where.append("m.warehouse_id = ?")
            movement_params.append(warehouse_id)
            sales_where.append("s.warehouse_id = ?")
            sales_params.append(warehouse_id)
            return_where.append("r.warehouse_id = ?")
            return_params.append(warehouse_id)
            inventory_where.append("warehouse_id = ?")
            inventory_params.append(warehouse_id)
        if search:
            product_search = "sku_no LIKE ? OR goods_no LIKE ? OR goods_name LIKE ? OR short_name LIKE ? OR spec_name LIKE ? OR barcode LIKE ?"
            movement_where.append(f"m.sku_no IN (SELECT sku_no FROM products WHERE {product_search})")
            sales_where.append(f"s.sku_no IN (SELECT sku_no FROM products WHERE {product_search})")
            return_where.append(f"r.sku_no IN (SELECT sku_no FROM products WHERE {product_search})")
            inventory_where.append(f"sku_no IN (SELECT sku_no FROM products WHERE {product_search})")
            needle = f"%{search}%"
            search_params = [needle] * 6
            movement_params.extend(search_params)
            sales_params.extend(search_params)
            return_params.extend(search_params)
            inventory_params.extend(search_params)

        move_filter = " AND ".join(movement_where)
        sales_filter = " AND ".join(sales_where)
        return_filter = " AND ".join(return_where)
        inv_filter = " AND ".join(inventory_where) if inventory_where else "1=1"
        inventory_having = {
            "positive": "HAVING SUM(stock_num) > 0",
            "zero": "HAVING SUM(stock_num) = 0",
            "negative": "HAVING SUM(stock_num) < 0",
            "unavailable": "HAVING SUM(available_num) <= 0",
        }.get(stock_status, "")
        common_ctes = f"""
            WITH s AS (
                SELECT s.sku_no, SUM(s.quantity) sales_qty,
                       SUM(s.paid_amount) sales_amount,
                       SUM(s.share_amount) share_amount
                FROM sales_lines s WHERE {sales_filter}
                GROUP BY s.sku_no
            ), m AS (
                SELECT m.sku_no,
                    SUM(CASE WHEN m.movement_type IN (-1,-6) THEN m.out_num ELSE 0 END) movement_sales_qty,
                    SUM(CASE WHEN m.movement_type=3 THEN m.in_num ELSE 0 END) movement_return_qty,
                    SUM(CASE WHEN m.movement_type=1 THEN m.in_num ELSE 0 END) purchase_qty
                FROM movements m
                WHERE {move_filter}
                GROUP BY m.sku_no
            ), r AS (
                SELECT r.sku_no, SUM(r.quantity) return_qty,
                       SUM(r.refund_amount) refund_amount
                FROM return_lines r
                WHERE {return_filter}
                GROUP BY r.sku_no
            ), inv AS (
                SELECT sku_no, SUM(stock_num) stock_num, SUM(available_num) available_num,
                       SUM(purchase_in_transit_num) purchase_in_transit_num,
                       SUM(stock_num * CASE WHEN avg_cost_price > 0 THEN avg_cost_price ELSE cost_price END) stock_value,
                       COUNT(*) warehouse_count, MAX(modified) modified
                FROM inventory_current WHERE {inv_filter} GROUP BY sku_no {inventory_having}
            ), u AS (
                SELECT sku_no FROM inv
                UNION SELECT sku_no FROM s
                UNION SELECT sku_no FROM m
                UNION SELECT sku_no FROM r
            )
        """
        result_filter = "WHERE inv.sku_no IS NOT NULL" if stock_status else ""
        common_params = sales_params + movement_params + return_params + inventory_params
        with self.connect() as connection:
            summary = connection.execute(
                common_ctes + f"""
                SELECT COALESCE(SUM(inv.stock_num),0) stock_num,
                       COALESCE(SUM(inv.available_num),0) available_num,
                       COALESCE(SUM(inv.purchase_in_transit_num),0) purchase_in_transit_num,
                       COALESCE(SUM(inv.stock_value),0) stock_value,
                       COALESCE(SUM(s.sales_qty),0) sales_qty,
                       COALESCE(SUM(r.return_qty),0) return_qty,
                       COALESCE(SUM(m.purchase_qty),0) purchase_qty,
                       COALESCE(SUM(s.sales_amount),0) sales_amount,
                       COALESCE(SUM(r.refund_amount),0) refund_amount,
                       COALESCE(SUM(COALESCE(s.sales_amount,0)-COALESCE(r.refund_amount,0)),0) net_revenue,
                       COALESCE(SUM((COALESCE(s.sales_qty,0)-COALESCE(r.return_qty,0))*COALESCE(p.retail_price,0)),0) estimated_revenue,
                       COALESCE(SUM(m.movement_sales_qty),0) movement_sales_qty,
                       COALESCE(SUM(m.movement_return_qty),0) movement_return_qty,
                       COUNT(inv.sku_no) sku_count,
                       COUNT(u.sku_no) result_count,
                       COALESCE(SUM(CASE WHEN inv.stock_num < 0 THEN 1 ELSE 0 END),0) negative_sku_count,
                       COALESCE(SUM(CASE WHEN inv.stock_num = 0 THEN 1 ELSE 0 END),0) zero_sku_count,
                       COALESCE(SUM(CASE WHEN inv.available_num <= 0 THEN 1 ELSE 0 END),0) unavailable_sku_count
                FROM u
                LEFT JOIN inv ON inv.sku_no=u.sku_no
                LEFT JOIN products p ON p.sku_no=u.sku_no
                LEFT JOIN s ON s.sku_no=u.sku_no
                LEFT JOIN m ON m.sku_no=u.sku_no
                LEFT JOIN r ON r.sku_no=u.sku_no
                {result_filter}
                """,
                common_params,
            ).fetchone()

            daily = connection.execute(
                f"""
                WITH sd AS (
                    SELECT s.sale_date date, SUM(s.quantity) sales_qty,
                           SUM(s.paid_amount) sales_amount
                    FROM sales_lines s WHERE {sales_filter}
                    GROUP BY s.sale_date
                ), md AS (
                    SELECT m.movement_date date,
                        SUM(CASE WHEN m.movement_type IN (-1,-6) THEN m.out_num ELSE 0 END) movement_sales_qty,
                        SUM(CASE WHEN m.movement_type=3 THEN m.in_num ELSE 0 END) movement_return_qty,
                        SUM(CASE WHEN m.movement_type=1 THEN m.in_num ELSE 0 END) purchase_qty
                    FROM movements m
                    WHERE {move_filter}
                    GROUP BY m.movement_date
                ), rd AS (
                    SELECT r.return_date date, SUM(r.quantity) return_qty,
                           SUM(r.refund_amount) refund_amount
                    FROM return_lines r WHERE {return_filter}
                    GROUP BY r.return_date
                ), dates AS (
                    SELECT date FROM sd UNION SELECT date FROM md UNION SELECT date FROM rd
                )
                SELECT dates.date,
                       COALESCE(sd.sales_qty,0) sales_qty,
                       COALESCE(rd.return_qty,0) return_qty,
                       COALESCE(md.purchase_qty,0) purchase_qty,
                       COALESCE(sd.sales_amount,0) sales_amount,
                       COALESCE(rd.refund_amount,0) refund_amount,
                       COALESCE(sd.sales_amount,0)-COALESCE(rd.refund_amount,0) net_revenue,
                       COALESCE(md.movement_sales_qty,0) movement_sales_qty,
                       COALESCE(md.movement_return_qty,0) movement_return_qty
                FROM dates
                LEFT JOIN sd ON sd.date=dates.date
                LEFT JOIN md ON md.date=dates.date
                LEFT JOIN rd ON rd.date=dates.date
                ORDER BY dates.date
                """,
                sales_params + movement_params + return_params,
            ).fetchall()

            rows = connection.execute(
                common_ctes + f"""
                SELECT u.sku_no, p.goods_no, p.goods_name, p.short_name, p.spec_name, p.unit_name,
                       p.retail_price, COALESCE(inv.stock_num,0) stock_num,
                       COALESCE(inv.available_num,0) available_num,
                       COALESCE(inv.purchase_in_transit_num,0) purchase_in_transit_num,
                       COALESCE(inv.stock_value,0) stock_value, inv.warehouse_count, inv.modified,
                       COALESCE(s.sales_qty,0) sales_qty, COALESCE(r.return_qty,0) return_qty,
                       COALESCE(m.purchase_qty,0) purchase_qty,
                       COALESCE(s.sales_qty,0)-COALESCE(r.return_qty,0) net_sales_qty,
                       COALESCE(s.sales_amount,0) sales_amount,
                       COALESCE(r.refund_amount,0) refund_amount,
                       COALESCE(s.sales_amount,0)-COALESCE(r.refund_amount,0) net_revenue,
                       (COALESCE(s.sales_qty,0)-COALESCE(r.return_qty,0))*COALESCE(p.retail_price,0) estimated_revenue,
                       COALESCE(m.movement_sales_qty,0) movement_sales_qty,
                       COALESCE(m.movement_return_qty,0) movement_return_qty
                FROM u
                LEFT JOIN products p ON p.sku_no=u.sku_no
                LEFT JOIN inv ON inv.sku_no=u.sku_no
                LEFT JOIN s ON s.sku_no=u.sku_no
                LEFT JOIN m ON m.sku_no=u.sku_no
                LEFT JOIN r ON r.sku_no=u.sku_no
                {result_filter}
                ORDER BY stock_num DESC, u.sku_no LIMIT ? OFFSET ?
                """,
                common_params + [limit, offset],
            ).fetchall()

            snapshot = connection.execute(
                "SELECT MAX(snapshot_date) snapshot_date FROM inventory_snapshots"
            ).fetchone()

        day_count = max((date.fromisoformat(end_date) - date.fromisoformat(start_date)).days + 1, 1)
        result_rows = []
        for row in rows:
            item = dict(row)
            daily_sales = item["net_sales_qty"] / day_count
            item["days_cover"] = round(item["available_num"] / daily_sales, 1) if daily_sales > 0 else None
            result_rows.append(item)
        summary_dict = dict(summary) if summary else {}
        summary_dict["net_sales_qty"] = summary_dict.get("sales_qty", 0) - summary_dict.get("return_qty", 0)
        return {
            "summary": summary_dict,
            "daily": [dict(row) for row in daily],
            "items": result_rows,
            "range": {"start": start_date, "end": end_date, "days": day_count},
            "pagination": {
                "total": int(summary_dict.get("result_count", 0)),
                "limit": limit,
                "offset": offset,
            },
            "snapshot_date": snapshot["snapshot_date"] if snapshot else None,
        }

    def warehouse_sku_sales(
        self,
        start_date: str,
        end_date: str,
        *,
        search: str = "",
        warehouse_id: str = "",
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        active_sales_filter = "NOT EXISTS (SELECT 1 FROM warehouse_master wm WHERE wm.warehouse_id=m.warehouse_id AND (wm.is_disabled=1 OR wm.role<>'sales'))"
        active_return_filter = "NOT EXISTS (SELECT 1 FROM warehouse_master wm WHERE wm.warehouse_id=m.warehouse_id AND wm.is_disabled=1)"
        where = [
            "m.movement_date BETWEEN ? AND ?",
            f"((m.movement_type IN (-1, -6) AND {active_sales_filter}) OR (m.movement_type=3 AND {active_return_filter}))",
        ]
        params: List[Any] = [start_date, end_date]
        end_day = date.fromisoformat(end_date)
        sales_3_start = (end_day - timedelta(days=2)).isoformat()
        sales_7_start = (end_day - timedelta(days=6)).isoformat()
        sales_15_start = (end_day - timedelta(days=14)).isoformat()
        sales_30_start = (end_day - timedelta(days=29)).isoformat()
        if warehouse_id:
            where.append("m.warehouse_id = ?")
            params.append(warehouse_id)
        if search:
            where.append(
                "m.sku_no IN (SELECT sku_no FROM products "
                "WHERE sku_no LIKE ? OR goods_no LIKE ? OR goods_name LIKE ? "
                "OR short_name LIKE ? OR spec_name LIKE ? OR barcode LIKE ?)"
            )
            needle = f"%{search}%"
            params.extend([needle] * 6)
        movement_filter = " AND ".join(where)
        rolling_where = [
            "m.movement_date BETWEEN ? AND ?",
            "m.movement_type IN (-1, -6)",
            active_sales_filter,
        ]
        rolling_params: List[Any] = [
            sales_7_start, end_date,
            sales_15_start, end_date,
            sales_3_start, end_date,
            sales_30_start, end_date,
        ]
        if warehouse_id:
            rolling_where.append("m.warehouse_id = ?")
            rolling_params.append(warehouse_id)
        if search:
            rolling_where.append(
                "m.sku_no IN (SELECT sku_no FROM products "
                "WHERE sku_no LIKE ? OR goods_no LIKE ? OR goods_name LIKE ? "
                "OR short_name LIKE ? OR spec_name LIKE ? OR barcode LIKE ?)"
            )
            rolling_params.extend([f"%{search}%"] * 6)
        rolling_filter = " AND ".join(rolling_where)
        inventory_where = [
            "NOT EXISTS (SELECT 1 FROM warehouse_master wm WHERE wm.warehouse_id=i.warehouse_id AND (wm.is_disabled=1 OR wm.role<>'sales'))"
        ]
        inventory_params: List[Any] = []
        if warehouse_id:
            inventory_where.append("i.warehouse_id = ?")
            inventory_params.append(warehouse_id)
        if search:
            inventory_where.append(
                "i.sku_no IN (SELECT sku_no FROM products "
                "WHERE sku_no LIKE ? OR goods_no LIKE ? OR goods_name LIKE ? "
                "OR short_name LIKE ? OR spec_name LIKE ? OR barcode LIKE ?)"
            )
            inventory_params.extend([f"%{search}%"] * 6)
        inventory_filter = " AND ".join(inventory_where)
        common_cte = f"""
            WITH performance AS (
                SELECT m.warehouse_id, MAX(m.warehouse_no) warehouse_no,
                       MAX(m.warehouse_name) warehouse_name, m.sku_no,
                       SUM(CASE WHEN m.movement_type IN (-1,-6) THEN m.out_num ELSE 0 END) sales_qty,
                       SUM(CASE WHEN m.movement_type=3 THEN m.in_num ELSE 0 END) return_qty,
                       COUNT(DISTINCT CASE WHEN m.movement_type IN (-1,-6) THEN m.movement_date END) sales_history_days,
                       COUNT(DISTINCT CASE WHEN m.movement_type IN (-1,-6) THEN m.src_order_no END) stockout_count
                FROM movements m
                WHERE {movement_filter}
                GROUP BY m.warehouse_id, m.sku_no
            ), rolling_sales AS (
                SELECT m.warehouse_id, m.sku_no,
                       SUM(CASE WHEN m.movement_date BETWEEN ? AND ? THEN m.out_num ELSE 0 END) sales_7d_qty,
                       SUM(CASE WHEN m.movement_date BETWEEN ? AND ? THEN m.out_num ELSE 0 END) sales_15d_qty,
                       SUM(CASE WHEN m.movement_date BETWEEN ? AND ? THEN m.out_num ELSE 0 END) sales_3d_qty,
                       SUM(m.out_num) sales_30d_qty
                FROM movements m
                WHERE {rolling_filter}
                GROUP BY m.warehouse_id, m.sku_no
            ), universe AS (
                SELECT warehouse_id, sku_no FROM performance
                UNION
                SELECT i.warehouse_id, i.sku_no
                FROM inventory_current i
                WHERE {inventory_filter}
            )
        """
        common_params = params + rolling_params + inventory_params
        with self.connect() as connection:
            summary = connection.execute(
                common_cte + """
                SELECT COUNT(*) row_count, COUNT(DISTINCT u.sku_no) sku_count,
                       COUNT(DISTINCT u.warehouse_id) warehouse_count,
                       COALESCE(SUM(pf.sales_qty),0) sales_qty,
                       COALESCE(SUM(pf.return_qty),0) return_qty,
                       COALESCE(SUM(pf.sales_qty-pf.return_qty),0) net_sales_qty,
                       COALESCE((SELECT SUM(sales_7d_qty) FROM rolling_sales),0) sales_7d_qty,
                       COALESCE((SELECT SUM(sales_15d_qty) FROM rolling_sales),0) sales_15d_qty,
                       COALESCE((SELECT SUM(sales_30d_qty) FROM rolling_sales),0) sales_30d_qty
                FROM universe u
                LEFT JOIN performance pf ON pf.warehouse_id=u.warehouse_id AND pf.sku_no=u.sku_no
                """,
                common_params,
            ).fetchone()
            rows = connection.execute(
                common_cte + """
                SELECT u.warehouse_id, COALESCE(pf.warehouse_no,i.warehouse_no,wm.warehouse_no,'') warehouse_no,
                       COALESCE(pf.warehouse_name,i.warehouse_name,wm.warehouse_name,'仓库 ' || u.warehouse_id) warehouse_name,
                       u.sku_no, p.goods_no, p.goods_name, p.short_name, p.spec_name,
                       p.spec_remark, p.supplier_name,
                       COALESCE(pf.sales_qty,0) sales_qty, COALESCE(pf.return_qty,0) return_qty,
                       COALESCE(pf.sales_qty,0)-COALESCE(pf.return_qty,0) net_sales_qty,
                       COALESCE(pf.sales_history_days,0) sales_history_days,
                       COALESCE(rs.sales_7d_qty,0) sales_7d_qty,
                       COALESCE(rs.sales_15d_qty,0) sales_15d_qty,
                       COALESCE(rs.sales_3d_qty,0) sales_3d_qty,
                       COALESCE(rs.sales_30d_qty,0) sales_30d_qty,
                       COALESCE(pf.stockout_count,0) stockout_count,
                       COALESCE(i.stock_num,0) stock_num,
                       COALESCE(i.available_num,0) available_num,
                       COALESCE(i.purchase_in_transit_num,0) purchase_in_transit_num
                FROM universe u
                LEFT JOIN performance pf ON pf.warehouse_id=u.warehouse_id AND pf.sku_no=u.sku_no
                LEFT JOIN rolling_sales rs ON rs.warehouse_id=u.warehouse_id AND rs.sku_no=u.sku_no
                LEFT JOIN products p ON p.sku_no=u.sku_no
                LEFT JOIN inventory_current i ON i.sku_no=u.sku_no AND i.warehouse_id=u.warehouse_id
                LEFT JOIN warehouse_master wm ON wm.warehouse_id=u.warehouse_id
                ORDER BY net_sales_qty DESC, pf.sales_qty DESC, pf.warehouse_name, pf.sku_no
                LIMIT ? OFFSET ?
                """,
                common_params + [limit, offset],
            ).fetchall()
        # Add trend and coverage facts used by the warehouse sales screen. The
        # 04 report applies its own 7/3/history-day demand rule to these facts.
        range_days = max((date.fromisoformat(end_date) - date.fromisoformat(start_date)).days + 1, 1)
        result_rows = []
        for row in rows:
            item = dict(row)
            sales_7 = to_float(item.get("sales_7d_qty"))
            sales_30 = to_float(item.get("sales_30d_qty"))
            if sales_30 > 0:
                daily_sales = sales_30 / 30
                trend_coefficient = (sales_7 / 7) / daily_sales
            elif sales_7 > 0:
                daily_sales = sales_7 / 7
                trend_coefficient = None
            elif to_float(item.get("sales_qty")) > 0:
                daily_sales = to_float(item.get("sales_qty")) / range_days
                trend_coefficient = None
            else:
                daily_sales = 0.0
                trend_coefficient = None
            supply = to_float(item.get("available_num")) + to_float(item.get("purchase_in_transit_num"))
            remaining_days = supply / daily_sales if daily_sales > 0 else None
            stockout_date = None
            if remaining_days is not None:
                try:
                    stockout_date = (
                        date.fromisoformat(end_date) + timedelta(days=max(math.ceil(remaining_days) - 1, 0))
                    ).isoformat()
                except OverflowError:
                    # Extremely slow sellers can have a mathematically valid
                    # coverage value beyond Python's supported calendar range.
                    stockout_date = None
            item["trend_coefficient"] = round(trend_coefficient, 3) if trend_coefficient is not None else None
            item["inventory_with_transit_days"] = (
                int(math.floor(remaining_days + 0.5)) if remaining_days is not None else None
            )
            item["estimated_stockout_date_with_transit"] = stockout_date
            item["coverage_daily_sales"] = round(daily_sales, 3)
            result_rows.append(item)
        return {
            "summary": dict(summary) if summary else {},
            "items": result_rows,
            "range": {"start": start_date, "end": end_date},
            "rolling_ranges": {
                "sales_7d": {"start": sales_7_start, "end": end_date},
                "sales_15d": {"start": sales_15_start, "end": end_date},
                "sales_30d": {"start": sales_30_start, "end": end_date},
            },
            "pagination": {
                "total": int(summary["row_count"] if summary else 0),
                "limit": limit,
                "offset": offset,
            },
        }

    def shop_sku_sales(
        self,
        start_date: str,
        end_date: str,
        *,
        search: str = "",
        shop_no: str = "",
        warehouse_id: str = "",
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Aggregate shipment orders and returns by shop and SKU.

        Returns that cannot be linked to an order detail are kept under the
        explicit ``未识别店铺`` bucket instead of being silently discarded.
        """
        sales_where = ["s.sale_date BETWEEN ? AND ?", "s.status >= 95", "s.quantity > 0"]
        sales_params: List[Any] = [start_date, end_date]
        if shop_no:
            sales_where.append("s.shop_no = ?")
            sales_params.append(shop_no)
        if warehouse_id:
            sales_where.append("s.warehouse_id = ?")
            sales_params.append(warehouse_id)
        if search:
            sales_where.append(
                "s.sku_no IN (SELECT sku_no FROM products WHERE sku_no LIKE ? OR goods_no LIKE ? "
                "OR goods_name LIKE ? OR short_name LIKE ? OR spec_name LIKE ? OR barcode LIKE ?)"
            )
            sales_params.extend([f"%{search}%"] * 6)
        sales_filter = " AND ".join(sales_where)

        return_where = [
            "m.movement_date BETWEEN ? AND ?",
            "m.movement_type = 3",
            "m.in_num > 0",
            "NOT EXISTS (SELECT 1 FROM warehouse_master wm WHERE wm.warehouse_id=m.warehouse_id AND wm.is_disabled=1)",
        ]
        return_params: List[Any] = [start_date, end_date]
        if warehouse_id:
            return_where.append("m.warehouse_id = ?")
            return_params.append(warehouse_id)
        if search:
            return_where.append(
                "m.sku_no IN (SELECT sku_no FROM products WHERE sku_no LIKE ? OR goods_no LIKE ? "
                "OR goods_name LIKE ? OR short_name LIKE ? OR spec_name LIKE ? OR barcode LIKE ?)"
            )
            return_params.extend([f"%{search}%"] * 6)
        return_filter = " AND ".join(return_where)
        shop_filter = "WHERE c.shop_no = ?" if shop_no else ""
        query = f"""
            WITH sales AS (
                SELECT s.shop_no, MAX(s.shop_name) shop_name, s.sku_no,
                       MAX(s.warehouse_id) warehouse_id,
                       SUM(s.quantity) sales_qty,
                       SUM(s.paid_amount) sales_amount
                FROM sales_lines s
                WHERE {sales_filter}
                GROUP BY s.shop_no, s.sku_no
            ), return_rows AS (
                SELECT m.* FROM movements m WHERE {return_filter}
            ), matched_returns AS (
                SELECT shop_no, MAX(shop_name) shop_name, sku_no, SUM(return_qty) return_qty
                FROM (
                    SELECT sl.shop_no, sl.shop_name, r.sku_no, SUM(r.in_num) return_qty
                    FROM return_rows r
                    JOIN sales_lines sl
                      ON sl.sku_no=r.sku_no AND sl.source_detail_id=r.source_detail_id
                    WHERE r.source_detail_id<>''
                    GROUP BY sl.shop_no, sl.shop_name, r.sku_no
                    UNION ALL
                    SELECT sl.shop_no, sl.shop_name, r.sku_no, SUM(r.in_num) return_qty
                    FROM return_rows r
                    JOIN sales_lines sl
                      ON sl.sku_no=r.sku_no AND sl.src_order_no=r.src_order_no
                    WHERE r.source_detail_id='' AND r.src_order_no<>''
                    GROUP BY sl.shop_no, sl.shop_name, r.sku_no
                    UNION ALL
                    SELECT '', '', r.sku_no, SUM(r.in_num) return_qty
                    FROM return_rows r
                    WHERE NOT EXISTS (
                        SELECT 1 FROM sales_lines sl
                        WHERE r.source_detail_id<>''
                          AND sl.sku_no=r.sku_no
                          AND sl.source_detail_id=r.source_detail_id
                    ) AND NOT EXISTS (
                        SELECT 1 FROM sales_lines sl
                        WHERE r.source_detail_id=''
                          AND r.src_order_no<>''
                          AND sl.sku_no=r.sku_no
                          AND sl.src_order_no=r.src_order_no
                    )
                    GROUP BY r.sku_no
                ) matched
                GROUP BY shop_no, sku_no
            ), combined AS (
                SELECT s.shop_no, s.shop_name, s.sku_no, s.warehouse_id,
                       s.sales_qty, COALESCE(r.return_qty,0) return_qty,
                       s.sales_amount
                FROM sales s
                LEFT JOIN matched_returns r ON r.shop_no=s.shop_no AND r.sku_no=s.sku_no
                UNION ALL
                SELECT r.shop_no, r.shop_name, r.sku_no, '' warehouse_id,
                       0 sales_qty, r.return_qty, 0 sales_amount
                FROM matched_returns r
                WHERE NOT EXISTS (
                    SELECT 1 FROM sales s WHERE s.shop_no=r.shop_no AND s.sku_no=r.sku_no
                )
            ), filtered AS (
                SELECT c.*, COALESCE(NULLIF(c.shop_name,''), '未识别店铺') display_shop_name,
                       p.goods_no, p.goods_name, p.short_name, p.spec_name
                FROM combined c
                LEFT JOIN products p ON p.sku_no=c.sku_no
                {shop_filter}
            )
        """
        params = sales_params + return_params + ([shop_no] if shop_no else [])
        with self.connect() as connection:
            summary = connection.execute(
                query + """
                SELECT COUNT(*) row_count, COUNT(DISTINCT shop_no) shop_count,
                       COUNT(DISTINCT sku_no) sku_count,
                       COALESCE(SUM(sales_qty),0) sales_qty,
                       COALESCE(SUM(return_qty),0) return_qty,
                       COALESCE(SUM(sales_qty-return_qty),0) net_sales_qty,
                       COALESCE(SUM(sales_amount),0) sales_amount
                FROM filtered
                """,
                params,
            ).fetchone()
            rows = connection.execute(
                query + """
                SELECT shop_no, display_shop_name shop_name, warehouse_id,
                       sku_no, goods_no, goods_name, short_name, spec_name,
                       sales_qty, return_qty, sales_qty-return_qty net_sales_qty,
                       sales_amount
                FROM filtered
                ORDER BY net_sales_qty DESC, sales_qty DESC, display_shop_name, sku_no
                LIMIT ? OFFSET ?
                """,
                params + [limit, offset],
            ).fetchall()
            shop_list_where = ["sale_date BETWEEN ? AND ?", "status >= 95", "quantity > 0"]
            shop_list_params: List[Any] = [start_date, end_date]
            if warehouse_id:
                shop_list_where.append("warehouse_id = ?")
                shop_list_params.append(warehouse_id)
            shops = connection.execute(
                f"""SELECT shop_no, COALESCE(NULLIF(MAX(shop_name),''),'未识别店铺') shop_name,
                           SUM(quantity) sales_qty
                    FROM sales_lines WHERE {' AND '.join(shop_list_where)}
                    GROUP BY shop_no ORDER BY sales_qty DESC, shop_no""",
                shop_list_params,
            ).fetchall()
        return {
            "summary": dict(summary) if summary else {},
            "items": [dict(row) for row in rows],
            "shops": [dict(row) for row in shops],
            "range": {"start": start_date, "end": end_date},
            "pagination": {"total": int(summary["row_count"] if summary else 0), "limit": limit, "offset": offset},
        }

    def inbound_analysis(
        self,
        start_date: str,
        end_date: str,
        *,
        search: str = "",
        warehouse_id: str = "",
        inbound_type: Optional[int] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        where = [
            "m.movement_date BETWEEN ? AND ?",
            "m.movement_type > 0",
            "m.in_num <> 0",
            "NOT EXISTS (SELECT 1 FROM warehouse_master wm WHERE wm.warehouse_id=m.warehouse_id AND wm.is_disabled=1)",
            "(m.movement_type=3 OR m.warehouse_id IN (SELECT warehouse_id FROM warehouse_master WHERE is_disabled=0 AND role='sales'))",
        ]
        params: List[Any] = [start_date, end_date]
        if warehouse_id:
            where.append("m.warehouse_id = ?")
            params.append(warehouse_id)
        if inbound_type is not None:
            where.append("m.movement_type = ?")
            params.append(inbound_type)
        if search:
            where.append(
                "m.sku_no IN (SELECT sku_no FROM products "
                "WHERE sku_no LIKE ? OR goods_no LIKE ? OR goods_name LIKE ? "
                "OR short_name LIKE ? OR spec_name LIKE ? OR barcode LIKE ?)"
            )
            params.extend([f"%{search}%"] * 6)

        movement_filter = " AND ".join(where)
        common_ctes = f"""
            WITH filtered AS (
                SELECT m.* FROM movements m WHERE {movement_filter}
            ), inbound AS (
                SELECT f.warehouse_id, MAX(f.warehouse_no) warehouse_no,
                       MAX(f.warehouse_name) warehouse_name, f.sku_no,
                       SUM(f.in_num) inbound_qty,
                       SUM(CASE WHEN f.movement_type=1 THEN f.in_num ELSE 0 END) purchase_qty,
                       SUM(CASE WHEN f.movement_type=2 THEN f.in_num ELSE 0 END) transfer_qty,
                       SUM(CASE WHEN f.movement_type=3 THEN f.in_num ELSE 0 END) return_qty,
                       SUM(CASE WHEN f.movement_type NOT IN (1,2,3) THEN f.in_num ELSE 0 END) other_qty,
                       COUNT(*) movement_count,
                       COUNT(DISTINCT NULLIF(f.src_order_no,'')) order_count,
                       MIN(f.event_time) first_inbound_time,
                       MAX(f.event_time) last_inbound_time
                FROM filtered f
                GROUP BY f.warehouse_id, f.sku_no
            )
        """
        with self.connect() as connection:
            summary = connection.execute(
                common_ctes + """
                SELECT (SELECT COUNT(*) FROM inbound) row_count,
                       COUNT(*) movement_count,
                       COUNT(DISTINCT sku_no) sku_count,
                       COUNT(DISTINCT warehouse_id) warehouse_count,
                       COALESCE(SUM(in_num),0) inbound_qty,
                       COALESCE(SUM(CASE WHEN movement_type=1 THEN in_num ELSE 0 END),0) purchase_qty,
                       COALESCE(SUM(CASE WHEN movement_type=2 THEN in_num ELSE 0 END),0) transfer_qty,
                       COALESCE(SUM(CASE WHEN movement_type=3 THEN in_num ELSE 0 END),0) return_qty,
                       COALESCE(SUM(CASE WHEN movement_type NOT IN (1,2,3) THEN in_num ELSE 0 END),0) other_qty
                FROM filtered
                """,
                params,
            ).fetchone()
            daily = connection.execute(
                common_ctes + """
                SELECT movement_date date, SUM(in_num) inbound_qty,
                       SUM(CASE WHEN movement_type=1 THEN in_num ELSE 0 END) purchase_qty,
                       SUM(CASE WHEN movement_type=2 THEN in_num ELSE 0 END) transfer_qty,
                       SUM(CASE WHEN movement_type=3 THEN in_num ELSE 0 END) return_qty,
                       SUM(CASE WHEN movement_type NOT IN (1,2,3) THEN in_num ELSE 0 END) other_qty
                FROM filtered GROUP BY movement_date ORDER BY movement_date
                """,
                params,
            ).fetchall()
            rows = connection.execute(
                common_ctes + """
                SELECT ib.warehouse_id, ib.warehouse_no,
                       COALESCE(NULLIF(ib.warehouse_name,''), wm.warehouse_name, ib.warehouse_no,
                                '仓库 ' || ib.warehouse_id) warehouse_name,
                       ib.sku_no, p.goods_no, p.goods_name, p.short_name, p.spec_name,
                       ib.inbound_qty, ib.purchase_qty, ib.transfer_qty, ib.return_qty,
                       ib.other_qty, ib.movement_count, ib.order_count,
                       ib.first_inbound_time, ib.last_inbound_time,
                       (SELECT GROUP_CONCAT(DISTINCT NULLIF(r.src_order_no,''))
                          FROM return_lines r
                         WHERE r.return_date BETWEEN ? AND ?
                           AND r.warehouse_id=ib.warehouse_id
                           AND r.sku_no=ib.sku_no) return_source_order_nos,
                       COALESCE(i.stock_num,0) stock_num,
                       COALESCE(i.available_num,0) available_num
                FROM inbound ib
                LEFT JOIN products p ON p.sku_no=ib.sku_no
                LEFT JOIN warehouse_master wm ON wm.warehouse_id=ib.warehouse_id
                LEFT JOIN inventory_current i
                  ON i.sku_no=ib.sku_no AND i.warehouse_id=ib.warehouse_id
                ORDER BY ib.inbound_qty DESC, warehouse_name, ib.sku_no
                LIMIT ? OFFSET ?
                """,
                params + [start_date, end_date, limit, offset],
            ).fetchall()

        summary_dict = dict(summary) if summary else {}
        return {
            "summary": summary_dict,
            "daily": [dict(row) for row in daily],
            "items": [dict(row) for row in rows],
            "range": {"start": start_date, "end": end_date},
            "filters": {"inbound_type": inbound_type},
            "pagination": {
                "total": int(summary_dict.get("row_count", 0)),
                "limit": limit,
                "offset": offset,
            },
        }

    def short_name_sales(
        self,
        start_date: str,
        end_date: str,
        *,
        search: str = "",
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Aggregate warehouse SKU performance by product short name.

        Each row combines every SKU and every active warehouse that shares the
        same product short name.  Warehouse-level rows are deliberately not
        returned: this screen is the company-wide counterpart to
        :meth:`warehouse_sku_sales`.
        """
        product_filter = ""
        product_params: List[Any] = []
        if search:
            product_filter = (
                "WHERE sku_no LIKE ? OR goods_no LIKE ? OR goods_name LIKE ? "
                "OR short_name LIKE ? OR spec_name LIKE ? OR barcode LIKE ?"
            )
            product_params.extend([f"%{search}%"] * 6)

        end_day = date.fromisoformat(end_date)
        sales_7_start = (end_day - timedelta(days=6)).isoformat()
        sales_15_start = (end_day - timedelta(days=14)).isoformat()
        sales_30_start = (end_day - timedelta(days=29)).isoformat()
        active_sales_filter = (
            "NOT EXISTS (SELECT 1 FROM warehouse_master wm "
            "WHERE wm.warehouse_id=m.warehouse_id "
            "AND (wm.is_disabled=1 OR wm.role<>'sales'))"
        )
        active_return_filter = (
            "NOT EXISTS (SELECT 1 FROM warehouse_master wm "
            "WHERE wm.warehouse_id=m.warehouse_id AND wm.is_disabled=1)"
        )
        active_inventory_filter = (
            "NOT EXISTS (SELECT 1 FROM warehouse_master wm "
            "WHERE wm.warehouse_id=i.warehouse_id "
            "AND (wm.is_disabled=1 OR wm.role<>'sales'))"
        )

        ctes = f"""
            WITH product_map AS (
                SELECT sku_no,
                       COALESCE(NULLIF(short_name,''), NULLIF(goods_no,''),
                                NULLIF(goods_name,''), sku_no) display_name,
                       CASE WHEN short_name<>'' THEN 0 ELSE 1 END is_fallback,
                       goods_name
                FROM products
                {product_filter}
            ), movement_summary AS (
                SELECT pm.display_name, MIN(pm.is_fallback) is_fallback,
                       SUM(CASE WHEN m.movement_type IN (-1,-6) THEN m.out_num ELSE 0 END) sales_qty,
                       SUM(CASE WHEN m.movement_type=3 THEN m.in_num ELSE 0 END) return_qty
                FROM movements m
                JOIN product_map pm ON pm.sku_no=m.sku_no
                WHERE m.movement_date BETWEEN ? AND ?
                  AND ((m.movement_type IN (-1,-6) AND {active_sales_filter})
                       OR (m.movement_type=3 AND {active_return_filter}))
                GROUP BY pm.display_name
            ), rolling_sales AS (
                SELECT pm.display_name,
                       SUM(CASE WHEN m.movement_date BETWEEN ? AND ? THEN m.out_num ELSE 0 END) sales_7d_qty,
                       SUM(CASE WHEN m.movement_date BETWEEN ? AND ? THEN m.out_num ELSE 0 END) sales_15d_qty,
                       SUM(m.out_num) sales_30d_qty
                FROM movements m
                JOIN product_map pm ON pm.sku_no=m.sku_no
                WHERE m.movement_date BETWEEN ? AND ?
                  AND m.movement_type IN (-1,-6)
                  AND {active_sales_filter}
                GROUP BY pm.display_name
            ), inventory_summary AS (
                SELECT pm.display_name,
                       SUM(i.stock_num) stock_num,
                       SUM(i.available_num) available_num,
                       SUM(i.purchase_in_transit_num) purchase_in_transit_num
                FROM inventory_current i
                JOIN product_map pm ON pm.sku_no=i.sku_no
                WHERE {active_inventory_filter}
                GROUP BY pm.display_name
            ), short_skus AS (
                SELECT DISTINCT pm.display_name, pm.sku_no
                FROM movements m
                JOIN product_map pm ON pm.sku_no=m.sku_no
                WHERE m.movement_date BETWEEN ? AND ?
                  AND ((m.movement_type IN (-1,-6) AND {active_sales_filter})
                       OR (m.movement_type=3 AND {active_return_filter}))
                UNION
                SELECT DISTINCT pm.display_name, pm.sku_no
                FROM inventory_current i
                JOIN product_map pm ON pm.sku_no=i.sku_no
                WHERE {active_inventory_filter}
            ), sku_summary AS (
                SELECT ss.display_name, MIN(pm.is_fallback) is_fallback,
                       COUNT(*) sku_count,
                       GROUP_CONCAT(DISTINCT NULLIF(pm.goods_name,'')) goods_names
                FROM short_skus ss
                JOIN product_map pm ON pm.sku_no=ss.sku_no
                GROUP BY ss.display_name
            ), name_universe AS (
                SELECT display_name FROM movement_summary
                UNION
                SELECT display_name FROM inventory_summary
            ), combined AS (
                SELECT u.display_name,
                       COALESCE(ms.is_fallback, ss.is_fallback, 0) is_fallback,
                       COALESCE(ss.sku_count,0) sku_count,
                       COALESCE(ss.goods_names,'') goods_names,
                       COALESCE(ms.sales_qty,0) sales_qty,
                       COALESCE(ms.return_qty,0) return_qty,
                       COALESCE(ms.sales_qty,0)-COALESCE(ms.return_qty,0) net_sales_qty,
                       COALESCE(rs.sales_7d_qty,0) sales_7d_qty,
                       COALESCE(rs.sales_15d_qty,0) sales_15d_qty,
                       COALESCE(rs.sales_30d_qty,0) sales_30d_qty,
                       COALESCE(inv.stock_num,0) stock_num,
                       COALESCE(inv.available_num,0) available_num,
                       COALESCE(inv.purchase_in_transit_num,0) purchase_in_transit_num
                FROM name_universe u
                LEFT JOIN movement_summary ms ON ms.display_name=u.display_name
                LEFT JOIN rolling_sales rs ON rs.display_name=u.display_name
                LEFT JOIN inventory_summary inv ON inv.display_name=u.display_name
                LEFT JOIN sku_summary ss ON ss.display_name=u.display_name
            )
        """
        cte_params = product_params + [
            start_date, end_date,
            sales_7_start, end_date,
            sales_15_start, end_date,
            sales_30_start, end_date,
            start_date, end_date,
        ]
        with self.connect() as connection:
            summary = connection.execute(
                ctes + """
                SELECT COUNT(*) row_count, COALESCE(SUM(sku_count),0) sku_count,
                       COALESCE(SUM(sales_qty),0) sales_qty,
                       COALESCE(SUM(return_qty),0) return_qty,
                       COALESCE(SUM(net_sales_qty),0) net_sales_qty,
                       COALESCE(SUM(sales_7d_qty),0) sales_7d_qty,
                       COALESCE(SUM(sales_15d_qty),0) sales_15d_qty,
                       COALESCE(SUM(sales_30d_qty),0) sales_30d_qty
                FROM combined
                """,
                cte_params,
            ).fetchone()
            rows = connection.execute(
                ctes + """
                SELECT * FROM combined
                ORDER BY net_sales_qty DESC, sales_qty DESC, display_name
                LIMIT ? OFFSET ?
                """,
                cte_params + [limit, offset],
            ).fetchall()

        range_days = max((date.fromisoformat(end_date) - date.fromisoformat(start_date)).days + 1, 1)
        result_rows = []
        for row in rows:
            item = dict(row)
            sales_7 = to_float(item.get("sales_7d_qty"))
            sales_30 = to_float(item.get("sales_30d_qty"))
            if sales_30 > 0:
                daily_sales = sales_30 / 30
                trend_coefficient = (sales_7 / 7) / daily_sales
            elif sales_7 > 0:
                daily_sales = sales_7 / 7
                trend_coefficient = None
            elif to_float(item.get("sales_qty")) > 0:
                daily_sales = to_float(item.get("sales_qty")) / range_days
                trend_coefficient = None
            else:
                daily_sales = 0.0
                trend_coefficient = None
            supply = to_float(item.get("available_num")) + to_float(item.get("purchase_in_transit_num"))
            remaining_days = supply / daily_sales if daily_sales > 0 else None
            stockout_date = None
            if remaining_days is not None:
                try:
                    stockout_date = (
                        end_day + timedelta(days=max(math.ceil(remaining_days) - 1, 0))
                    ).isoformat()
                except OverflowError:
                    stockout_date = None
            item["trend_coefficient"] = round(trend_coefficient, 3) if trend_coefficient is not None else None
            item["inventory_with_transit_days"] = (
                int(math.floor(remaining_days + 0.5)) if remaining_days is not None else None
            )
            item["estimated_stockout_date_with_transit"] = stockout_date
            item["coverage_daily_sales"] = round(daily_sales, 3)
            result_rows.append(item)
        return {
            "summary": dict(summary) if summary else {},
            "items": result_rows,
            "range": {"start": start_date, "end": end_date},
            "rolling_ranges": {
                "sales_7d": {"start": sales_7_start, "end": end_date},
                "sales_15d": {"start": sales_15_start, "end": end_date},
                "sales_30d": {"start": sales_30_start, "end": end_date},
            },
            "pagination": {
                "total": int(summary["row_count"] if summary else 0),
                "limit": limit,
                "offset": offset,
            },
        }

    def replenishment_analysis(
        self,
        start_date: str,
        end_date: str,
        *,
        mode: str = "replenishment",
        search: str = "",
        limit: int = 100,
        offset: int = 0,
        target_days: int = 30,
        clearance_status: str = "",
        alert_status: str = "",
        alert_mode: str = "",
        warehouse_id: str = "",
    ) -> Dict[str, Any]:
        day_count = max((date.fromisoformat(end_date) - date.fromisoformat(start_date)).days + 1, 1)
        sales3_start = (date.fromisoformat(end_date) - timedelta(days=2)).isoformat()
        sales3_days = 3
        sales7_start = (date.fromisoformat(end_date) - timedelta(days=6)).isoformat()
        sales7_days = 7
        sales15_start = (date.fromisoformat(end_date) - timedelta(days=14)).isoformat()
        trend_start = (date.fromisoformat(end_date) - timedelta(days=29)).isoformat()
        trend_days = 30
        filters = [
            "p.goods_name NOT LIKE '%运费%'",
            "p.goods_name NOT LIKE '%寄付%'",
            "p.goods_name NOT LIKE '%赠品%'",
            "p.goods_name NOT LIKE '%赠送%'",
            "p.goods_name NOT LIKE '%不发货%'",
            "p.goods_name NOT LIKE '%差价%'",
        ]
        if mode == "replenishment":
            # 清仓款不参与补货，但符合严格条件时需在库存预警中单独提示。
            pass
        elif mode == "clearance":
            filters.append("p.product_structure = '清仓款'")
        else:
            raise ValueError("invalid analysis mode")
        params: List[Any] = []
        if search:
            filters.append(
                "(p.sku_no LIKE ? OR p.goods_no LIKE ? OR p.goods_name LIKE ? "
                "OR p.short_name LIKE ? OR p.spec_name LIKE ? OR p.barcode LIKE ?)"
            )
            params.extend([f"%{search}%"] * 6)
        product_filter = " AND ".join(filters)
        warehouse_filter = "WHERE u.warehouse_id=?" if warehouse_id else ""
        ctes = f"""
            WITH eligible_products AS (
                SELECT p.sku_no,p.goods_no,p.goods_name,p.short_name,p.spec_name,p.unit_name,
                       p.category,p.product_structure,p.moq,p.production_days,p.metadata_status,
                       p.supplier_id,p.supplier_no,p.supplier_name,p.spec_remark,
                       p.purchase_price,p.erp_price
                FROM products p WHERE {product_filter}
            ), history_coverage AS (
                SELECT COUNT(DISTINCT m.movement_date) sales_history_days
                FROM movements m
                WHERE m.movement_date BETWEEN ? AND ?
                  AND m.movement_type IN (-1,-6)
                  AND m.warehouse_id IN (SELECT warehouse_id FROM warehouse_master WHERE is_disabled=0 AND role='sales')
            ), sales_3 AS (
                SELECT m.sku_no,m.warehouse_id,SUM(m.out_num) sales_3d_qty
                FROM movements m JOIN eligible_products p ON p.sku_no=m.sku_no
                WHERE m.movement_date BETWEEN ? AND ?
                  AND m.movement_type IN (-1,-6)
                  AND m.warehouse_id IN (SELECT warehouse_id FROM warehouse_master WHERE is_disabled=0 AND role='sales')
                GROUP BY m.sku_no,m.warehouse_id
            ), sales_7 AS (
                SELECT m.sku_no,m.warehouse_id,SUM(m.out_num) sales_qty
                FROM movements m JOIN eligible_products p ON p.sku_no=m.sku_no
                WHERE m.movement_date BETWEEN ? AND ?
                  AND m.movement_type IN (-1,-6)
                  AND m.warehouse_id IN (SELECT warehouse_id FROM warehouse_master WHERE is_disabled=0 AND role='sales')
                GROUP BY m.sku_no,m.warehouse_id
            ), sales_30 AS (
                SELECT m.sku_no,m.warehouse_id,SUM(m.out_num) sales_30d_qty
                FROM movements m JOIN eligible_products p ON p.sku_no=m.sku_no
                WHERE m.movement_date BETWEEN ? AND ?
                  AND m.movement_type IN (-1,-6)
                  AND m.warehouse_id IN (SELECT warehouse_id FROM warehouse_master WHERE is_disabled=0 AND role='sales')
                GROUP BY m.sku_no,m.warehouse_id
            ), sales_15 AS (
                SELECT m.sku_no,m.warehouse_id,SUM(m.out_num) sales_15d_qty
                FROM movements m JOIN eligible_products p ON p.sku_no=m.sku_no
                WHERE m.movement_date BETWEEN ? AND ?
                  AND m.movement_type IN (-1,-6)
                  AND m.warehouse_id IN (SELECT warehouse_id FROM warehouse_master WHERE is_disabled=0 AND role='sales')
                GROUP BY m.sku_no,m.warehouse_id
            ), returns AS (
                SELECT m.sku_no,m.warehouse_id,SUM(m.in_num) return_qty
                FROM movements m JOIN eligible_products p ON p.sku_no=m.sku_no
                WHERE m.movement_date BETWEEN ? AND ? AND m.movement_type=3
                  AND m.warehouse_id IN (SELECT warehouse_id FROM warehouse_master WHERE is_disabled=0 AND role='sales')
                GROUP BY m.sku_no,m.warehouse_id
            ), inventory AS (
                SELECT i.sku_no,i.warehouse_id,MAX(i.warehouse_no) warehouse_no,
                       MAX(i.warehouse_name) warehouse_name,SUM(i.stock_num) stock_num,
                       SUM(i.available_num) available_num,
                       SUM(i.purchase_in_transit_num) purchase_in_transit_num
                FROM inventory_current i
                JOIN eligible_products p ON p.sku_no=i.sku_no
                LEFT JOIN warehouse_master w ON w.warehouse_id=i.warehouse_id
                WHERE COALESCE(w.is_disabled,0)=0 AND COALESCE(w.role,'sales')='sales'
                GROUP BY i.sku_no,i.warehouse_id
            ), universe AS (
                SELECT sku_no,warehouse_id FROM inventory
                UNION SELECT sku_no,warehouse_id FROM sales_7
                UNION SELECT sku_no,warehouse_id FROM sales_30
            ), facts AS (
                SELECT p.sku_no,p.goods_no,p.goods_name,p.short_name,p.spec_name,p.unit_name,
                       p.category,p.product_structure,p.moq,p.production_days,p.metadata_status,
                       p.supplier_id,p.supplier_no,p.supplier_name,p.spec_remark,
                       p.purchase_price,p.erp_price,
                       u.warehouse_id,COALESCE(i.warehouse_no,w.warehouse_no,'') warehouse_no,
                       COALESCE(NULLIF(i.warehouse_name,''),w.warehouse_name,'仓库 ' || u.warehouse_id) warehouse_name,
                       COALESCE(i.stock_num,0) stock_num,
                       COALESCE(i.available_num,0) available_num,
                       COALESCE(i.purchase_in_transit_num,0) purchase_in_transit_num,
                       1 warehouse_count,
                       COALESCE(s3.sales_3d_qty,0) sales_3d_qty,
                       COALESCE(s7.sales_qty,0) sales_qty,
                       COALESCE(s7.sales_qty,0) sales_7d_qty,
                       COALESCE(s15.sales_15d_qty,0) sales_15d_qty,
                       COALESCE(s30.sales_30d_qty,0) sales_30d_qty,
                       COALESCE(r.return_qty,0) return_qty,
                       COALESCE(s3.sales_3d_qty,0)/? avg_3d_daily,
                       COALESCE(s7.sales_qty,0)/? avg_7d_daily,
                       COALESCE(s30.sales_30d_qty,0)/? avg_30d_daily,
                       CASE WHEN COALESCE(s30.sales_30d_qty,0)>0
                            THEN (COALESCE(s7.sales_qty,0)/?) / (COALESCE(s30.sales_30d_qty,0)/?) END trend_coefficient,
                       COALESCE(s7.sales_qty,0)/? daily_sales,
                       CASE WHEN COALESCE(s7.sales_qty,0)>0
                            THEN COALESCE(i.available_num,0)*?/s7.sales_qty END coverage_days
                FROM universe u JOIN eligible_products p ON p.sku_no=u.sku_no
                LEFT JOIN inventory i ON i.sku_no=u.sku_no AND i.warehouse_id=u.warehouse_id
                LEFT JOIN warehouse_master w ON w.warehouse_id=u.warehouse_id
                LEFT JOIN sales_3 s3 ON s3.sku_no=u.sku_no AND s3.warehouse_id=u.warehouse_id
                LEFT JOIN sales_7 s7 ON s7.sku_no=u.sku_no AND s7.warehouse_id=u.warehouse_id
                LEFT JOIN sales_15 s15 ON s15.sku_no=u.sku_no AND s15.warehouse_id=u.warehouse_id
                LEFT JOIN sales_30 s30 ON s30.sku_no=u.sku_no AND s30.warehouse_id=u.warehouse_id
                LEFT JOIN returns r ON r.sku_no=u.sku_no AND r.warehouse_id=u.warehouse_id
                {warehouse_filter}
            ), model AS (
                SELECT facts.*,h.sales_history_days,
                       CASE WHEN h.sales_history_days>=30 THEN avg_7d_daily*0.4 + avg_30d_daily*0.6
                            WHEN h.sales_history_days>=7 THEN avg_7d_daily
                            WHEN h.sales_history_days>=3 THEN avg_3d_daily
                            WHEN h.sales_history_days>0 THEN sales_3d_qty*1.0/h.sales_history_days
                            ELSE 0 END forecast_daily_sales,
                       CASE WHEN h.sales_history_days>=30 THEN '7日/30日加权'
                            WHEN h.sales_history_days>=7 THEN '7日平均'
                            WHEN h.sales_history_days>=3 THEN '3日平均'
                            WHEN h.sales_history_days>0 THEN '近期平均'
                            ELSE '暂无销量' END forecast_basis
                FROM facts CROSS JOIN history_coverage h
            ), coverage AS (
                SELECT model.*,
                       CASE WHEN forecast_daily_sales>0 THEN available_num/forecast_daily_sales END forecast_coverage_days,
                       CASE WHEN forecast_daily_sales>0 THEN (available_num+purchase_in_transit_num)/forecast_daily_sales END projected_coverage_days
                FROM model
            ), classified AS (
                SELECT coverage.*,
                       CASE
                         WHEN available_num<=0 THEN 'cleared'
                         WHEN sales_qty=0 THEN 'stagnant'
                         WHEN purchase_in_transit_num>0 THEN 'transit'
                         ELSE 'in_progress'
                       END clearance_status
                FROM coverage
            ), alert_candidates AS (
                SELECT classified.*,
                       CASE
                         WHEN product_structure='清仓款' THEN '清仓预警'
                         WHEN projected_coverage_days>365 THEN '严重积压'
                         WHEN projected_coverage_days>180 THEN '中度积压'
                         ELSE '库存预警'
                       END recommendation,
                       CASE
                         WHEN product_structure='清仓款' THEN 0
                         WHEN projected_coverage_days>365 THEN 1
                         WHEN projected_coverage_days>180 THEN 2
                         ELSE 3
                       END recommendation_order
                FROM classified
                WHERE (
                    COALESCE(product_structure, '') <> '清仓款'
                    AND projected_coverage_days > 90
                ) OR (
                    product_structure='清仓款'
                    AND available_num > 0
                    AND (
                        (
                            forecast_coverage_days >= 0
                            AND forecast_coverage_days < 2
                        )
                        OR available_num < 5
                    )
                )
            )
        """
        base_params = params + [
            trend_start,
            end_date,
            sales3_start,
            end_date,
            sales7_start,
            end_date,
            trend_start,
            end_date,
            sales15_start,
            end_date,
            sales7_start,
            end_date,
            sales3_days,
            sales7_days,
            trend_days,
            sales7_days,
            trend_days,
            day_count,
            day_count,
        ] + ([warehouse_id] if warehouse_id else [])
        if mode == "clearance":
            clearance_where = "WHERE clearance_status = ?" if clearance_status else ""
            clearance_params = [clearance_status] if clearance_status else []
            summary_sql = f"""
                SELECT COUNT(*) row_count,SUM(sales_qty) sales_qty,SUM(return_qty) return_qty,
                       SUM(available_num) available_qty,SUM(purchase_in_transit_num) in_transit_qty,
                       SUM(CASE WHEN available_num<=0 THEN 1 ELSE 0 END) cleared_count,
                       SUM(CASE WHEN sales_qty=0 AND available_num>0 THEN 1 ELSE 0 END) stagnant_count
                FROM classified
                {clearance_where}
            """
            rows_sql = f"""
                SELECT *,
                       0 suggested_restock,
                       CASE
                         WHEN trend_coefficient IS NULL THEN '无30日基线'
                         WHEN trend_coefficient < 0.5 THEN '大幅下滑'
                         WHEN trend_coefficient < 0.8 THEN '小幅下滑'
                         WHEN trend_coefficient < 1.2 THEN '平稳'
                         WHEN trend_coefficient < 1.8 THEN '稳步上涨'
                         ELSE '爆发增长'
                       END trend_status,
                       '清仓款停止补货，仅跟踪库存去化进度' trend_action,
                       CASE
                         WHEN available_num<=0 THEN '已清完'
                         WHEN sales_qty=0 THEN '清仓停滞'
                         WHEN purchase_in_transit_num>0 THEN '在途待处理'
                         ELSE '清仓进行中'
                       END recommendation,
                       CASE
                         WHEN available_num<=0 THEN 3
                         WHEN sales_qty=0 THEN 1
                         WHEN purchase_in_transit_num>0 THEN 2
                         ELSE 0
                       END recommendation_order
                FROM classified
                {clearance_where}
                ORDER BY recommendation_order,sales_qty DESC,available_num DESC
                LIMIT ? OFFSET ?
            """
        else:
            alert_conditions = []
            alert_params = []
            if alert_mode == "normal":
                alert_conditions.append("recommendation <> '清仓预警'")
            elif alert_mode == "clearance":
                alert_conditions.append("recommendation = '清仓预警'")
            if alert_status:
                alert_conditions.append("recommendation=?")
                alert_params.append(alert_status)
            alert_where = f"WHERE {' AND '.join(alert_conditions)}" if alert_conditions else ""
            summary_sql = f"""
                SELECT COUNT(*) row_count,SUM(sales_qty) sales_qty,SUM(return_qty) return_qty,
                       SUM(CASE WHEN recommendation='严重积压' THEN 1 ELSE 0 END) critical_count,
                       SUM(CASE WHEN recommendation='中度积压' THEN 1 ELSE 0 END) warning_count,
                       SUM(CASE WHEN recommendation='库存预警' THEN 1 ELSE 0 END) attention_count,
                       SUM(CASE WHEN recommendation='清仓预警' THEN 1 ELSE 0 END) clearance_alert_count
                FROM alert_candidates
                {alert_where}
            """
            rows_sql = f"""
                SELECT *,
                       CASE
                         WHEN trend_coefficient IS NULL THEN 1.0
                         WHEN trend_coefficient < 0.5 THEN 0.50
                         WHEN trend_coefficient < 0.8 THEN 0.60
                         WHEN trend_coefficient < 1.2 THEN 1.00
                         WHEN trend_coefficient < 1.8 THEN 1.20
                         ELSE 1.40
                       END trend_adjustment,
                       forecast_daily_sales trend_adjusted_daily_sales,
                       CASE WHEN product_structure='清仓款' THEN 0
                            ELSE MAX(0,forecast_daily_sales * CASE
                              WHEN trend_coefficient IS NULL THEN 1.0
                              WHEN trend_coefficient < 0.5 THEN 0.50
                              WHEN trend_coefficient < 0.8 THEN 0.60
                              WHEN trend_coefficient < 1.2 THEN 1.00
                              WHEN trend_coefficient < 1.8 THEN 1.20
                              ELSE 1.40
                            END *?-available_num-purchase_in_transit_num)
                       END suggested_restock,
                       CASE
                         WHEN trend_coefficient IS NULL THEN '无30日基线'
                         WHEN trend_coefficient < 0.5 THEN '大幅下滑'
                         WHEN trend_coefficient < 0.8 THEN '小幅下滑'
                         WHEN trend_coefficient < 1.2 THEN '平稳'
                         WHEN trend_coefficient < 1.8 THEN '稳步上涨'
                         ELSE '爆发增长'
                       END trend_status,
                       CASE
                         WHEN trend_coefficient IS NULL THEN '暂无30日销量基线，先观察'
                         WHEN trend_coefficient < 0.5 THEN '下单量下调60%-80%，观察销量变化'
                         WHEN trend_coefficient < 0.8 THEN '下单量下调20%-40%'
                         WHEN trend_coefficient < 1.2 THEN '按正常月度预测'
                       WHEN trend_coefficient < 1.8 THEN '下单量提升20%-50%'
                       ELSE '下单量提升50%-100%，加急在途入库'
                       END trend_action
                FROM alert_candidates
                {alert_where}
                ORDER BY recommendation_order,projected_coverage_days ASC,sales_qty DESC
                LIMIT ? OFFSET ?
            """
        with self.connect() as connection:
            summary = connection.execute(
                ctes + summary_sql,
                base_params + (clearance_params if mode == "clearance" else alert_params),
            ).fetchone()
            row_params = (
                base_params + clearance_params + [limit, offset]
                if mode == "clearance"
                else base_params + [target_days] + alert_params + [limit, offset]
            )
            rows = connection.execute(
                ctes + rows_sql,
                row_params,
            ).fetchall()
            snapshot = connection.execute(
                "SELECT MAX(snapshot_date) snapshot_date FROM inventory_snapshots"
            ).fetchone()
        result_items = [dict(row) for row in rows]
        for item in result_items:
            if item.get("recommendation") in {"库存预警", "中度积压", "严重积压"}:
                item["trend_action"] = "含采购在途的预测库存超过 90 天，暂不建议补货。"
            item["recommendation_note"] = (
                "参数待补充，当前使用通用库存天数公式"
                if item.get("metadata_status") != "已配置" else ""
            )
            item["trend_coefficient"] = (
                round(float(item["trend_coefficient"]), 3)
                if item.get("trend_coefficient") is not None else None
            )
            for key in (
                "avg_3d_daily", "avg_7d_daily", "avg_30d_daily", "forecast_daily_sales",
                "trend_adjustment", "trend_adjusted_daily_sales",
            ):
                item[key] = round(float(item.get(key) or 0), 3)
            for key in ("forecast_coverage_days", "projected_coverage_days"):
                coverage_value = float(item[key]) if item.get(key) is not None else None
                # 积压预警采用严格的大于 90 天条件。向上显示含在途天数，避免
                # 90.01 天被截断为 90.0 天而与预警口径看起来不一致。
                round_up = (
                    key == "projected_coverage_days"
                    and item.get("recommendation") in {"库存预警", "中度积压", "严重积压"}
                )
                item[key] = (
                    (math.ceil(coverage_value * 10) if round_up else math.floor(coverage_value * 10)) / 10
                    if coverage_value is not None else None
                )
        return {
            "summary": dict(summary) if summary else {},
            "items": result_items,
            "mode": mode,
            "range": {"start": start_date, "end": end_date, "days": day_count},
            "target_days": target_days,
            "inventory_alert_threshold_days": 90 if mode == "replenishment" else None,
            "clearance_alert_rule": "清仓款满足以下任一条件即预警：预测库存天数低于 2 天，或可用库存 1-4 件；零库存不预警" if mode == "replenishment" else None,
            "alert_status": alert_status if mode == "replenishment" else None,
            "alert_mode": alert_mode if mode == "replenishment" else None,
            "trend_range": {"start": trend_start, "end": end_date, "days": trend_days},
            "snapshot_date": snapshot["snapshot_date"] if snapshot else None,
            "pagination": {
                "total": int(summary["row_count"] if summary else 0),
                "limit": limit,
                "offset": offset,
            },
        }

    def purchase_plan(
        self,
        start_date: str,
        end_date: str,
        *,
        search: str = "",
        limit: int = 100,
        offset: int = 0,
        target_days: int = 30,
        trend_min: Optional[float] = None,
        trend_max: Optional[float] = None,
        plan_status: str = "",
        warehouse_id: str = "",
    ) -> Dict[str, Any]:
        """Plan direct-to-warehouse purchasing after reserving transferable surplus."""
        plan = self._warehouse_planning_rows(start_date, end_date, search=search)
        end = date.fromisoformat(end_date)
        rows: List[Dict[str, Any]] = []
        for item in plan["rows"]:
            # Clearance SKUs are managed in the clearance workflow and must not
            # appear in the purchasing plan or its procurement summaries.  Keep
            # the structure check as a fallback for rows loaded from older
            # databases where the derived flag may not be present.
            structure = str(item.get("product_structure") or "").strip()
            if item.get("is_clearance") or structure == "清仓款":
                continue
            coefficient = item.get("trend_coefficient")
            if coefficient is not None:
                if trend_min is not None and coefficient < trend_min:
                    continue
                if trend_max is not None and coefficient >= trend_max:
                    continue
            row = dict(item)
            # Purchase quantity follows the workbook target directly. Current
            # stock, purchase in-transit and suggested transfers affect stock
            # coverage, shortage severity and order timing only; they no longer
            # reduce the quantity to order.
            remaining = max(0.0, float(row["required_qty"]))
            # A blank MOQ defaults to 100 units. An explicitly configured
            # metadata row with "无" remains the zero-MOQ exception.
            if row.get("moq") in (None, "") and row.get("metadata_status") != "已配置":
                row["moq"] = 100
            moq = float(row.get("moq") or 0)
            raw_calculated_qty = math.ceil(remaining) if remaining > 0 else 0
            minimum_qty = math.ceil(moq)
            if raw_calculated_qty > 0 and raw_calculated_qty < minimum_qty:
                # A quantity below MOQ remains an explicit MOQ uplift and is not
                # rounded to 50, so the exception remains visible to operations.
                calculated_qty = raw_calculated_qty
                final_qty = minimum_qty
            elif raw_calculated_qty > 0:
                # The 50-unit rule applies once the calculated requirement has
                # reached MOQ. Values 1-10 round down to the lower multiple and
                # values 11+ round up to the next multiple.
                calculated_qty = _round_purchase_qty_to_50(raw_calculated_qty)
                if calculated_qty < minimum_qty:
                    calculated_qty = math.ceil(minimum_qty / 50) * 50
                final_qty = calculated_qty
            else:
                calculated_qty = 0
                final_qty = 0
            low_demand_observation = bool(
                row.get("sales_30d_qty", 0) > 0
                and row.get("trend_coefficient") is not None
                and row["trend_coefficient"] < 0.5
                and row.get("daily_sales", 0) < 1
            )
            if row["production_days"] is None:
                status = "参数待补充"
                final_qty = 0
            elif low_demand_observation or row["is_clearance"]:
                status = "低销量观察"
                # Keep the row visible for review, but do not turn a low-demand
                # SKU into a real purchase action merely because of MOQ.
                final_qty = 0
            elif row["daily_sales"] <= 0:
                status = "暂无销量"
                final_qty = 0
            elif row["transfer_qty"] > 0 and remaining <= 0:
                status = "建议调拨"
            elif row["transfer_qty"] > 0 and remaining > 0:
                status = "调拨后仍缺货"
            elif remaining <= 0:
                status = "暂不下单"
            elif row["shortage_before_arrival"]:
                status = "交期内预计缺货"
            elif row["suggested_order_date"] <= end.isoformat():
                status = "应立即下单"
            else:
                status = "计划下单"
            plan_reason = self._plan_reason(row, remaining)
            if low_demand_observation:
                plan_reason = (
                    f"近30日销量 {float(row.get('sales_30d_qty') or 0):.0f} 件，"
                    f"日销量 {float(row.get('daily_sales') or 0):.3f} 件，"
                    f"趋势系数 {float(row.get('trend_coefficient') or 0):.3f}；"
                    "低销量观察，建议转清仓评估，不按最低起订量下单。"
                )
            row.update({
                "raw_order_qty": round(remaining, 3),
                "purchase_after_transfer_qty": round(remaining, 3),
                "calculated_order_qty": int(calculated_qty),
                "final_order_qty": int(final_qty),
                "moq_uplift_qty": int(max(final_qty - calculated_qty, 0)),
                "moq_applied": bool(final_qty > calculated_qty),
                "plan_status": status,
                "plan_reason": plan_reason,
                "low_demand_observation": low_demand_observation,
            })
            if low_demand_observation or row["is_clearance"]:
                row["suggested_order_date"] = None
                row["estimated_arrival_date"] = None
                row["next_scheduled_arrival_date"] = None
            rows.append(row)

        if warehouse_id:
            rows = [row for row in rows if row.get("warehouse_id") == warehouse_id]
        week_deadline = (end + timedelta(days=7)).isoformat()
        for row in rows:
            is_purchase = int(row.get("final_order_qty") or 0) > 0
            # “应立即下单”只表示理论排期已经到今天，并不必然等于严重缺货。
            # 严重程度只按今天下单能否在现有供应耗尽前到货判断：含在途
            # 覆盖天数严格小于完整交付周期时才标红；等于周期时仍按本周下单。
            severe_shortage = bool(row.get("shortage_before_arrival"))
            missing_parameters = row.get("production_days") is None
            due_soon = bool(
                not severe_shortage and not missing_parameters and not row.get("low_demand_observation")
                and row.get("suggested_order_date")
                and end.isoformat() <= row["suggested_order_date"] <= week_deadline
            )
            if missing_parameters:
                severity = "missing_parameters"
            elif row.get("low_demand_observation") or row.get("is_clearance"):
                severity = "low_demand"
            elif severe_shortage:
                severity = "urgent"
            elif due_soon:
                severity = "within_week"
            elif row.get("suggested_order_date"):
                severity = "later"
            else:
                severity = "no_action"
            row["is_purchase_action"] = is_purchase
            row["is_severe_shortage"] = severe_shortage
            row["is_due_within_week"] = due_soon
            row["timing_label"] = (
                "低销量观察（清仓候选）" if row.get("low_demand_observation") or row.get("is_clearance") else
                "严重缺货" if severe_shortage else
                "本周下单" if due_soon else
                "后续排期" if row.get("suggested_order_date") else row.get("plan_status") or "暂不下单"
            )
            row["procurement_severity"] = severity
        # All enabled SKU rows in the five operational warehouses remain
        # visible. Rows without a production cycle are informational only.
        if plan_status:
            rows = [row for row in rows if row.get("plan_status") == plan_status]
        rows.sort(key=lambda row: (
            row.get("suggested_order_date") is None,
            row.get("suggested_order_date") or "9999-12-31",
            {"urgent": 0, "within_week": 1, "later": 2, "low_demand": 3, "missing_parameters": 4, "no_action": 5}.get(row.get("procurement_severity"), 6),
            row.get("warehouse_name") or "",
            -float(row.get("final_order_qty") or 0),
        ))
        total = len(rows)
        page_items = rows[offset:offset + limit]
        actionable_rows = [row for row in rows if not row.get("low_demand_observation")]
        return {
            "items": page_items,
            "summary": {
                "row_count": total,
                "order_now_count": sum(1 for row in rows if row.get("plan_status") == "应立即下单"),
                "planned_count": sum(1 for row in rows if row.get("plan_status") == "计划下单"),
                "pending_count": sum(1 for row in rows if row.get("plan_status") == "参数待补充"),
                "risk_count": sum(1 for row in rows if row.get("plan_status") == "交期内预计缺货"),
                # Keep the summary aligned with the red urgent rows in the
                # purchase-plan table. Low-demand/clearance observations may
                # still have a shortage flag at the raw coverage level, but
                # they are intentionally not treated as urgent purchase rows.
                "severe_shortage_count": sum(1 for row in rows if row.get("procurement_severity") == "urgent"),
                "due_within_week_count": sum(1 for row in rows if row["is_due_within_week"]),
                "future_purchase_count": sum(1 for row in rows if row["is_purchase_action"] and not row["is_severe_shortage"] and not row["is_due_within_week"]),
                "low_demand_count": sum(1 for row in rows if row.get("low_demand_observation")),
                "transfer_count": sum(1 for row in rows if float(row.get("transfer_qty") or 0) > 0),
                "moq_applied_count": sum(1 for row in actionable_rows if row.get("moq_applied")),
                "total_calculated_order_qty": int(sum(float(row.get("calculated_order_qty") or 0) for row in actionable_rows)),
                "total_moq_uplift_qty": int(sum(float(row.get("moq_uplift_qty") or 0) for row in actionable_rows)),
                "total_order_qty": int(sum(float(row.get("final_order_qty") or 0) for row in actionable_rows)),
            },
            "range": {"start": start_date, "end": end_date, "days": (end - date.fromisoformat(start_date)).days + 1},
            "target_days": target_days,
            "planning_basis": "仅计算五个运营仓；日销量按7日均值40%+30日均值60%计算，采购量按周销量A匹配生产周期公式并应用趋势倍率，直接使用目标库存，不扣减可用库存、采购在途或建议调拨。先按预计缺货日减完整交付周期倒推理论下单日，再按日期分级。含在途库存天数严格小于完整交付周期时标为紧急；宏博/铠博/博凯基础款的每月5日、20日作为执行参考，不用于放大紧急等级；缺生产周期仅展示不计算。",
            "trend_filter": {"min": trend_min, "max": trend_max},
            "snapshot_date": self._latest_snapshot_date(),
            "pagination": {"total": total, "limit": limit, "offset": offset},
        }

    def transfer_plan(
        self, start_date: str, end_date: str, *, search: str = "", warehouse_id: str = "",
        limit: int = 100, offset: int = 0,
    ) -> Dict[str, Any]:
        """List actual source-to-target allocations produced by the warehouse plan."""
        plan = self._warehouse_planning_rows(start_date, end_date, search=search)
        rows = [dict(row) for row in plan["transfers"] if not warehouse_id or row["target_warehouse_id"] == warehouse_id or row["source_warehouse_id"] == warehouse_id]
        rows.sort(key=lambda row: (row["target_warehouse_name"], row["sku_no"], -row["transfer_qty"]))
        total = len(rows)
        return {
            "items": rows[offset:offset + limit],
            "summary": {
                "row_count": total,
                "transfer_qty": int(sum(row["transfer_qty"] for row in rows)),
                "sku_count": len({row["sku_no"] for row in rows}),
                "target_warehouse_count": len({row["target_warehouse_id"] for row in rows}),
            },
            "range": {"start": start_date, "end": end_date},
            "planning_basis": "仅处理未来 7 天内预计缺货的启用销售仓；来源仓先保留自身需求，余量才可调拨。停用、退货、残次和虚拟仓不参与调拨。",
            "pagination": {"total": total, "limit": limit, "offset": offset},
        }

    def _plan_reason(self, row: Dict[str, Any], remaining: float) -> str:
        if row["is_clearance"]:
            return "清仓款不参与采购；按目标仓库存覆盖天数跟踪去化。"
        if row["production_days"] is None:
            return "缺少生产周期，无法推断直发采购日期。"
        base = f"生产{row['production_days']}天 + 提前{row['advance_days']}天"
        if row["buffer_days"]:
            base += " + 物流/预留5天"
        if row.get("fixed_order_date"):
            base += "；理论下单日按库存倒推，5日/20日仅作执行参考"
        quantity_basis = (
            f"周销量A={float(row.get('weekly_sales') or 0):g}，"
            f"目标{float(row.get('target_week_multiplier') or 0):g}A，"
            f"趋势倍率{float(row.get('trend_purchase_multiplier') or 1):g}，"
            f"目标库存{float(row.get('target_stock_qty') or 0):g}件；"
        )
        transfer_note = f"；另建议跨仓调拨 {int(row['transfer_qty'])} 件" if row["transfer_qty"] else ""
        return (
            f"{quantity_basis}{base}；采购量直接按目标库存计算，不扣减可用库存、"
            f"采购在途或建议调拨，取整前为 {math.ceil(remaining)} 件{transfer_note}。"
        )

    def _warehouse_planning_rows(self, start_date: str, end_date: str, *, search: str = "") -> Dict[str, Any]:
        """Build warehouse/SKU demand facts and reserve source stock before transfer allocation."""
        end = date.fromisoformat(end_date)
        sales3_start = (end - timedelta(days=2)).isoformat()
        sales7_start = (end - timedelta(days=6)).isoformat()
        sales30_start = (end - timedelta(days=29)).isoformat()
        filters = [
            "p.goods_name NOT LIKE '%运费%'", "p.goods_name NOT LIKE '%寄付%'",
            "p.goods_name NOT LIKE '%赠品%'", "p.goods_name NOT LIKE '%赠送%'",
            "p.goods_name NOT LIKE '%不发货%'", "p.goods_name NOT LIKE '%差价%'",
            # WangDian marks disabled/deleted SKU specs in the goods payload.
            # Keep legacy/demo rows without these fields enabled by default.
            "COALESCE(json_extract(p.raw_json, '$.deleted'), 0) = 0",
            "COALESCE(json_extract(p.raw_json, '$.goods_status'), 0) = 0",
        ]
        params: List[Any] = []
        if search:
            filters.append("(p.sku_no LIKE ? OR p.goods_no LIKE ? OR p.goods_name LIKE ? OR p.short_name LIKE ? OR p.spec_name LIKE ? OR p.barcode LIKE ?)")
            params.extend([f"%{search}%"] * 6)
        product_filter = " AND ".join(filters)
        with self.connect() as connection:
            active_names = {
                str(row["warehouse_name"] or "")
                for row in connection.execute(
                    "SELECT warehouse_name FROM warehouse_master WHERE is_disabled=0 AND role='sales'"
                ).fetchall()
            }
        # Procurement is intentionally scoped to the five operational report
        # warehouses. A local/demo database without those names should produce
        # no procurement rows rather than silently widening the scope.
        warehouse_names = tuple(name for name in PROCUREMENT_WAREHOUSE_NAMES if name in active_names) or ("__NO_PROCUREMENT_WAREHOUSE__",)
        warehouse_placeholders = ",".join("?" for _ in warehouse_names)
        sql = f"""
            WITH sales AS (
                SELECT m.sku_no,m.warehouse_id,
                       SUM(CASE WHEN m.movement_date BETWEEN ? AND ? THEN m.out_num ELSE 0 END) sales_3d_qty,
                       SUM(CASE WHEN m.movement_date BETWEEN ? AND ? THEN m.out_num ELSE 0 END) sales_7d_qty,
                       SUM(CASE WHEN m.movement_date BETWEEN ? AND ? THEN m.out_num ELSE 0 END) sales_30d_qty
                FROM movements m
                WHERE m.movement_type IN (-1,-6) AND m.movement_date BETWEEN ? AND ?
                GROUP BY m.sku_no,m.warehouse_id
            ), universe AS (
                SELECT i.sku_no,i.warehouse_id FROM inventory_current i
                JOIN warehouse_master iw ON iw.warehouse_id=i.warehouse_id
                WHERE iw.is_disabled=0 AND iw.role='sales'
                  AND iw.warehouse_name IN ({warehouse_placeholders})
                UNION SELECT s.sku_no,s.warehouse_id FROM sales s
                JOIN warehouse_master sw ON sw.warehouse_id=s.warehouse_id
                WHERE sw.is_disabled=0 AND sw.role='sales'
                  AND sw.warehouse_name IN ({warehouse_placeholders})
            )
            SELECT p.sku_no,p.goods_no,p.goods_name,p.short_name,p.spec_name,p.category,p.product_structure,
                   p.moq,p.production_days,p.production_line,p.production_capacity,p.metadata_status,
                   p.spec_remark,p.supplier_name,p.purchase_price,p.erp_price,
                   u.warehouse_id,COALESCE(NULLIF(i.warehouse_no,''),wm.warehouse_no,'') warehouse_no,
                   COALESCE(NULLIF(i.warehouse_name,''),wm.warehouse_name,'仓库 ' || u.warehouse_id) warehouse_name,
                   COALESCE(wm.role,'sales') warehouse_role,
                   COALESCE(wm.transfer_source_enabled,0) transfer_source_enabled,
                   COALESCE(i.stock_num,0) stock_num,COALESCE(i.available_num,0) available_num,
                   COALESCE(i.purchase_in_transit_num,0) purchase_in_transit_num,
                   COALESCE(s.sales_3d_qty,0) sales_3d_qty,COALESCE(s.sales_7d_qty,0) sales_7d_qty,COALESCE(s.sales_30d_qty,0) sales_30d_qty
            FROM universe u
            JOIN products p ON p.sku_no=u.sku_no
            LEFT JOIN inventory_current i ON i.sku_no=u.sku_no AND i.warehouse_id=u.warehouse_id
            LEFT JOIN warehouse_master wm ON wm.warehouse_id=u.warehouse_id
            LEFT JOIN sales s ON s.sku_no=u.sku_no AND s.warehouse_id=u.warehouse_id
            WHERE {product_filter} AND COALESCE(wm.is_disabled,0)=0
              AND COALESCE(wm.role,'sales')='sales'
              AND wm.warehouse_name IN ({warehouse_placeholders})
        """
        with self.connect() as connection:
            history = connection.execute(
                "SELECT COUNT(DISTINCT movement_date) count FROM movements WHERE movement_type IN (-1,-6) AND movement_date BETWEEN ? AND ?",
                (sales30_start, end_date),
            ).fetchone()
            warehouse_params = list(warehouse_names)
            db_rows = connection.execute(
                sql,
                [sales3_start, end_date, sales7_start, end_date, sales30_start, end_date, sales30_start, end_date]
                + warehouse_params + warehouse_params + params + warehouse_params,
            ).fetchall()
        history_days = int(history["count"] or 0)

        def next_fixed(anchor: date) -> date:
            candidates = []
            for offset in (-1, 0, 1, 2):
                month = anchor.month - 1 + offset
                year, month = anchor.year + month // 12, month % 12 + 1
                candidates.extend((date(year, month, 5), date(year, month, 20)))
            return min(value for value in candidates if value >= anchor)

        def fixed_before(deadline: date) -> date:
            candidates = []
            for offset in (-2, -1, 0, 1, 2):
                month = deadline.month - 1 + offset
                year, month = deadline.year + month // 12, month % 12 + 1
                candidates.extend((date(year, month, 5), date(year, month, 20)))
            eligible = [value for value in candidates if end <= value <= deadline]
            return max(eligible) if eligible else next_fixed(end)

        def next_thursday(anchor: date) -> date:
            days = (3 - anchor.weekday()) % 7
            return anchor + timedelta(days=days)

        def fixed_supplier(name: str) -> bool:
            # Keep compatibility with both names encountered in WangDian data.
            return any(token in name for token in ("宏博", "铠博", "博凯"))

        rows: List[Dict[str, Any]] = []
        for raw in db_rows:
            row = dict(raw)
            avg3, avg7, avg30 = row["sales_3d_qty"] / 3, row["sales_7d_qty"] / 7, row["sales_30d_qty"] / 30
            if history_days >= 30:
                forecast, basis = avg7 * .4 + avg30 * .6, "7日/30日加权（40%/60%）"
            elif history_days >= 7:
                forecast, basis = avg7, "7日平均"
            elif history_days >= 3:
                forecast, basis = avg3, "3日平均"
            elif history_days:
                forecast, basis = row["sales_3d_qty"] / history_days, "近期平均"
            else:
                forecast, basis = 0.0, "暂无销量"
            coefficient = avg7 / avg30 if row["sales_30d_qty"] else None
            adjustment = _trend_purchase_multiplier(coefficient)
            trend_status = "无30日基线" if coefficient is None else "大幅下滑" if coefficient < .5 else "小幅下滑" if coefficient < .8 else "平稳" if coefficient < 1.2 else "稳步上涨" if coefficient < 1.8 else "爆发增长"
            # The workbook applies the trend multiplier to the purchase target,
            # not to daily sales.  Keeping daily sales independent avoids
            # counting the same trend twice when calculating coverage days.
            daily = forecast
            supplier_name = str(row["supplier_name"] or "")
            hongbo_or_bokai = fixed_supplier(supplier_name)
            production = int(row["production_days"]) if row["production_days"] not in (None, "") else (30 if hongbo_or_bokai else None)
            fixed = hongbo_or_bokai and row["product_structure"] == "基础款"
            advance = {15: 2, 25: 3, 30: 5}.get(production, max(1, round(production / 6))) if production else None
            buffer = 5 if fixed else 0
            lead = production + advance + buffer if production and advance else None
            purchase_category = _purchase_category(row.get("category"))
            target_week_multiplier = _target_week_multiplier(production)
            weekly_sales = float(row["sales_7d_qty"] or 0)
            target_stock_qty = (
                weekly_sales * target_week_multiplier * adjustment
                if target_week_multiplier is not None else 0.0
            )
            supply = float(row["available_num"] or 0) + float(row["purchase_in_transit_num"] or 0)
            if lead and daily > 0:
                projected_coverage = supply / daily
                stockout = end + timedelta(days=max(0, math.ceil(projected_coverage) - 1)) if supply > 0 else end
                due = stockout - timedelta(days=lead)
                # Establish the inventory-driven theoretical schedule first.
                order = max(end, due)
                arrival = order + timedelta(days=lead)
                arrival_days = lead + max((order - end).days, 0)
                next_arrival = None
                horizon = arrival_days
                shortage_before_arrival = _is_lead_time_shortage(projected_coverage, lead)
                if shortage_before_arrival:
                    order = end
                    arrival = order + timedelta(days=lead)
                    arrival_days = lead
                elif fixed:
                    # Fixed-date products use the latest fixed date that still
                    # meets the inventory-driven due date; if the due date is
                    # already past, use the next available fixed date.
                    order = fixed_before(due)
                    arrival = order + timedelta(days=lead)
                    next_arrival = arrival
                    horizon = max((arrival - end).days, 0)
                elif row["product_structure"] == "基础款":
                    # Non-fixed basic products are ordered every Thursday.
                    order = next_thursday(max(end, due))
                    arrival = order + timedelta(days=lead)
                    next_arrival = arrival
                    horizon = max((arrival - end).days, 0)
                else:
                    # Amplified/test products use the workbook's inventory-day
                    # trigger. The trigger is a normal schedule rule; a value
                    # below full lead time remains the separate urgent rule.
                    trigger_days = 20 if production <= 20 else 30 if production <= 25 else 35
                    if projected_coverage < trigger_days:
                        order = end
                        arrival = order + timedelta(days=lead)
                        horizon = lead
                    else:
                        order = max(end, due)
                        arrival = order + timedelta(days=lead)
                        horizon = max((arrival - end).days, 0)
                # The workbook quantity is target stock, not demand during the
                # planning horizon. Keep required_qty as that target so the
                # purchase calculation subtracts stock and in-transit directly.
                required = target_stock_qty
            else:
                stockout = due = order = arrival = next_arrival = None
                horizon = 0
                shortage_before_arrival = False
                required = target_stock_qty
            is_clearance = row["product_structure"] == "清仓款"
            coverage = (float(row["available_num"] or 0) / daily) if daily else None
            projected_coverage = (
                (float(row["available_num"] or 0) + float(row["purchase_in_transit_num"] or 0)) / daily
                if daily else None
            )
            clearance_status = "已清完" if float(row["available_num"] or 0) <= 0 else "清仓即将完成" if coverage is not None and coverage < 2 else "清仓进行中"
            row.update({
                "avg_3d_daily": round(avg3, 3), "avg_7d_daily": round(avg7, 3), "avg_30d_daily": round(avg30, 3),
                "forecast_daily_sales": round(forecast, 3), "forecast_basis": basis,
                "trend_coefficient": round(coefficient, 3) if coefficient is not None else None,
                "trend_status": trend_status, "trend_adjustment": adjustment, "trend_purchase_multiplier": adjustment,
                "trend_adjusted_daily_sales": round(daily, 3), "daily_sales": daily,
                "purchase_category": purchase_category, "weekly_sales": weekly_sales,
                "target_week_multiplier": target_week_multiplier, "target_stock_qty": round(target_stock_qty, 3),
                "purchase_formula": f"{int(target_week_multiplier)}A×{adjustment:g}" if target_week_multiplier is not None else "缺少生产周期",
                "production_days": production, "advance_days": advance, "buffer_days": buffer, "lead_days": lead,
                "order_window": "固定下单日（每月5日、20日）" if fixed else ("每周四下单" if row["product_structure"] == "基础款" else "库存天数阈值触发"),
                "suggested_order_date": order.isoformat() if order else None, "theoretical_order_date": due.isoformat() if due else None,
                "fixed_order_date_reference": next_fixed(order).isoformat() if fixed and order else None,
                "estimated_arrival_date": arrival.isoformat() if arrival else None,
                "next_scheduled_arrival_date": next_arrival.isoformat() if next_arrival else None,
                "estimated_stockout_date": stockout.isoformat() if stockout else None, "planning_horizon_days": horizon,
                "supply_qty": supply, "required_qty": required, "shortage_before_arrival": shortage_before_arrival,
                "transfer_qty": 0.0, "is_clearance": is_clearance, "forecast_coverage_days": coverage,
                "projected_coverage_days": projected_coverage,
                "plan_status": clearance_status if is_clearance else "",
                "fixed_order_date": fixed,
            })
            rows.append(row)

        transfers: List[Dict[str, Any]] = []
        by_sku: Dict[str, List[Dict[str, Any]]] = {}
        for row in rows:
            # A sales warehouse with no recent shipment can still be a valid source;
            # its own demand reserve is simply zero.
            if not row["is_clearance"] and row["production_days"]:
                by_sku.setdefault(row["sku_no"], []).append(row)
        for sku_rows in by_sku.values():
            sources = []
            for row in sku_rows:
                if not row["transfer_source_enabled"] or row["warehouse_role"] != "sales":
                    continue
                # Retain each source warehouse's own demand through its next planned arrival.
                reserve = float(row["required_qty"])
                transferable = max(0.0, float(row["supply_qty"]) - reserve)
                if transferable:
                    sources.append([row, transferable])
            # A transfer is an immediate operating action. Do not move stock today
            # for a theoretical shortfall in a future procurement cycle.
            transfer_deadline = (end + timedelta(days=7)).isoformat()
            targets = sorted(
                (
                    row for row in sku_rows
                    if row["warehouse_role"] == "sales"
                    and row["required_qty"] > row["supply_qty"]
                    and row["estimated_stockout_date"]
                    and row["estimated_stockout_date"] <= transfer_deadline
                ),
                key=lambda row: row["required_qty"] - row["supply_qty"], reverse=True,
            )
            for target in targets:
                need = float(target["required_qty"]) - float(target["supply_qty"])
                for source in sources:
                    source_row, available = source
                    if source_row["warehouse_id"] == target["warehouse_id"] or need <= 0 or available <= 0:
                        continue
                    quantity = min(need, available)
                    quantity = math.floor(quantity)
                    if quantity <= 0:
                        continue
                    source[1] -= quantity
                    need -= quantity
                    target["transfer_qty"] += quantity
                    transfers.append({
                        "sku_no": target["sku_no"], "short_name": target["short_name"], "goods_name": target["goods_name"], "spec_name": target["spec_name"],
                        "source_warehouse_id": source_row["warehouse_id"], "source_warehouse_name": source_row["warehouse_name"],
                        "target_warehouse_id": target["warehouse_id"], "target_warehouse_name": target["warehouse_name"],
                        "transfer_qty": int(quantity), "target_shortage_qty": math.ceil(float(target["required_qty"]) - float(target["supply_qty"])),
                        "target_daily_sales": round(float(target["daily_sales"]), 3), "target_stockout_date": target["estimated_stockout_date"],
                    })
        return {"rows": rows, "transfers": transfers}

    def _latest_snapshot_date(self) -> Optional[str]:
        with self.connect() as connection:
            row = connection.execute("SELECT MAX(snapshot_date) snapshot_date FROM inventory_snapshots").fetchone()
        return row["snapshot_date"] if row else None

    def sku_detail(self, sku_no: str, start_date: str, end_date: str) -> Optional[Dict[str, Any]]:
        with self.connect() as connection:
            product = connection.execute(
                "SELECT * FROM products WHERE sku_no=?", (sku_no,)
            ).fetchone()
            if not product:
                return None
            warehouses = connection.execute(
                """
                SELECT warehouse_id, warehouse_no, warehouse_name, stock_num, available_num,
                       cost_price, avg_cost_price, purchase_in_transit_num, modified
                FROM inventory_current i
                WHERE sku_no=?
                  AND NOT EXISTS (
                    SELECT 1 FROM warehouse_master wm
                    WHERE wm.warehouse_id=i.warehouse_id
                      AND (wm.is_disabled=1 OR wm.role<>'sales')
                  )
                ORDER BY warehouse_name
                """,
                (sku_no,),
            ).fetchall()
            daily = connection.execute(
                """
                WITH sd AS (
                    SELECT sale_date date, SUM(quantity) sales_qty,
                           SUM(paid_amount) sales_amount
                    FROM sales_lines s
                    WHERE sku_no=? AND sale_date BETWEEN ? AND ? AND status >= 95
                      AND NOT EXISTS (SELECT 1 FROM warehouse_master wm WHERE wm.warehouse_id=s.warehouse_id AND (wm.is_disabled=1 OR wm.role<>'sales'))
                    GROUP BY sale_date
                ), rd AS (
                    SELECT return_date date, SUM(quantity) return_qty,
                           SUM(refund_amount) refund_amount
                    FROM return_lines r
                    WHERE sku_no=? AND return_date BETWEEN ? AND ?
                      AND NOT EXISTS (SELECT 1 FROM warehouse_master wm WHERE wm.warehouse_id=r.warehouse_id AND wm.is_disabled=1)
                    GROUP BY return_date
                ), md AS (
                    SELECT movement_date date,
                           SUM(CASE WHEN movement_type=1 THEN in_num ELSE 0 END) purchase_qty
                    FROM movements m
                    WHERE sku_no=? AND movement_date BETWEEN ? AND ?
                      AND NOT EXISTS (SELECT 1 FROM warehouse_master wm WHERE wm.warehouse_id=m.warehouse_id AND (wm.is_disabled=1 OR wm.role<>'sales'))
                    GROUP BY movement_date
                ), dates AS (
                    SELECT date FROM sd UNION SELECT date FROM rd UNION SELECT date FROM md
                )
                SELECT dates.date, COALESCE(sd.sales_qty,0) sales_qty,
                       COALESCE(rd.return_qty,0) return_qty,
                       COALESCE(md.purchase_qty,0) purchase_qty,
                       COALESCE(sd.sales_amount,0) sales_amount,
                       COALESCE(rd.refund_amount,0) refund_amount,
                       COALESCE(sd.sales_amount,0)-COALESCE(rd.refund_amount,0) net_revenue
                FROM dates LEFT JOIN sd ON sd.date=dates.date
                LEFT JOIN rd ON rd.date=dates.date LEFT JOIN md ON md.date=dates.date
                ORDER BY dates.date
                """,
                (sku_no, start_date, end_date, sku_no, start_date, end_date, sku_no, start_date, end_date),
            ).fetchall()
            financials = connection.execute(
                """
                SELECT COALESCE((SELECT SUM(paid_amount) FROM sales_lines
                                 WHERE sku_no=? AND sale_date BETWEEN ? AND ? AND status >= 95),0) sales_amount,
                       COALESCE((SELECT SUM(refund_amount) FROM return_lines
                                 WHERE sku_no=? AND return_date BETWEEN ? AND ?),0) refund_amount
                """,
                (sku_no, start_date, end_date, sku_no, start_date, end_date),
            ).fetchone()
            recent = connection.execute(
                """
                SELECT movement_date, event_time, movement_name, movement_type, in_num, out_num,
                       src_order_no, warehouse_name
                FROM movements WHERE sku_no=? AND movement_date BETWEEN ? AND ?
                ORDER BY event_time DESC LIMIT 30
                """,
                (sku_no, start_date, end_date),
            ).fetchall()
        product_dict = dict(product)
        product_dict.pop("raw_json", None)
        financial_dict = dict(financials) if financials else {"sales_amount": 0, "refund_amount": 0}
        financial_dict["net_revenue"] = financial_dict["sales_amount"] - financial_dict["refund_amount"]
        return {
            "product": product_dict,
            "warehouses": [dict(row) for row in warehouses],
            "daily": [dict(row) for row in daily],
            "financials": financial_dict,
            "recent_movements": [dict(row) for row in recent],
        }

    def seed_demo(self) -> None:
        if not self.is_empty():
            return
        today = date.today()
        products = []
        inventory = []
        movements = []
        sales_orders = []
        return_orders = []
        names = [
            ("SKU-1001", "轻盈保温杯", "雾白 500ml", 129),
            ("SKU-1002", "轻盈保温杯", "墨黑 500ml", 129),
            ("SKU-2031", "旅行收纳袋", "海盐蓝 六件套", 89),
            ("SKU-2032", "旅行收纳袋", "石墨灰 六件套", 89),
            ("SKU-3108", "柔软浴巾", "云朵白 70x140", 69),
            ("SKU-4112", "桌面阅读灯", "暖白 标准版", 199),
            ("SKU-5110", "折叠晴雨伞", "深海蓝", 79),
            ("SKU-6204", "便携充电线", "USB-C 1m", 39),
            ("SKU-7201", "厨房储物罐", "透明 1.2L", 59),
            ("SKU-8302", "棉质家居拖鞋", "米白 38-39", 49),
            ("SKU-8303", "棉质家居拖鞋", "深灰 42-43", 49),
            ("SKU-9107", "无线蓝牙音箱", "曜石黑", 259),
        ]
        for index, (sku, goods, spec, price) in enumerate(names):
            products.append({"sku_no": sku, "goods_no": f"G{index+1:04}", "goods_name": goods, "spec_name": spec, "retail_price": price, "unit_name": "件"})
            stock = 18 + (index * 17) % 180
            inventory.append({"spec_no": sku, "warehouse_id": "1", "warehouse_no": "MAIN", "warehouse_name": "主仓", "stock_num": stock, "available_num": max(stock - index % 7, 0), "avg_cost_price": price * 0.42})
            if index % 4 == 0:
                inventory.append({"spec_no": sku, "warehouse_id": "2", "warehouse_no": "EAST", "warehouse_name": "华东仓", "stock_num": 20 + index, "available_num": 18 + index, "avg_cost_price": price * 0.43})
            for days_ago in range(44, -1, -1):
                day = today - timedelta(days=days_ago)
                sales = (index * 3 + days_ago * 2) % 11 + (4 if day.weekday() < 5 else 7)
                event = f"{day.isoformat()} 16:20:00"
                movements.append({"sku_no": sku, "warehouse_id": "1", "warehouse_name": "主仓", "in_out_type": "销售订单", "out_num": sales, "create_date": event, "src_id": f"S{index}{days_ago}", "src_detail_id": f"SD{index}{days_ago}", "src_order_no": f"JY{day.strftime('%y%m%d')}{index:03}"})
                sales_orders.append({"stockout_id": f"S{index}{days_ago}", "order_no": f"CK{day.strftime('%y%m%d')}{index:03}", "src_order_no": f"JY{day.strftime('%y%m%d')}{index:03}", "consign_time": event, "warehouse_id": "1", "warehouse_name": "主仓", "status": 95, "details_list": [{"rec_id": f"SD{index}{days_ago}", "src_order_detail_id": f"SD{index}{days_ago}", "spec_no": sku, "goods_name": goods, "spec_name": spec, "num": sales, "paid": round(sales * price * 0.92, 2), "retail_price": price}]})
                if (days_ago + index) % 9 == 0:
                    return_num = 1 + index % 2
                    movements.append({"sku_no": sku, "warehouse_id": "1", "warehouse_name": "主仓", "in_out_type": "退货入库", "in_num": return_num, "create_date": f"{day.isoformat()} 11:10:00", "src_id": f"R{index}{days_ago}", "src_detail_id": f"RD{index}{days_ago}", "src_order_no": f"RK{day.strftime('%y%m%d')}{index:03}"})
                    return_orders.append({"stockin_id": f"R{index}{days_ago}", "order_no": f"RK{day.strftime('%y%m%d')}{index:03}", "stockin_time": f"{day.isoformat()} 11:10:00", "warehouse_id": "1", "warehouse_name": "主仓", "status": 80, "details_list": [{"rec_id": f"RD{index}{days_ago}", "spec_no": sku, "goods_name": goods, "spec_name": spec, "num": return_num, "actual_refund_amount": round(return_num * price * 0.92, 2)}]})
                if days_ago in (30, 12) and index % 3 == 0:
                    movements.append({"sku_no": sku, "warehouse_id": "1", "warehouse_name": "主仓", "in_out_type": "采购入库", "in_num": 80, "create_date": f"{day.isoformat()} 09:00:00", "src_id": f"P{index}{days_ago}", "src_detail_id": f"PD{index}{days_ago}", "src_order_no": f"RK{day.strftime('%y%m%d')}P{index:02}"})
        self.upsert_products(products)
        self.upsert_movements(movements)
        self.upsert_sales_orders(sales_orders)
        self.upsert_return_orders(return_orders)
        self.upsert_inventory(inventory, today.isoformat())
        run_id = self.start_sync(today.isoformat())
        self.finish_sync(run_id, status="demo", movement_count=len(movements), inventory_count=len(inventory), sales_count=len(sales_orders), return_count=len(return_orders))
