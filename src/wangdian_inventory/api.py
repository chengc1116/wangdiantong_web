"""Read-only FastAPI service for the existing WangDian SQLite database.

The service deliberately keeps writes and WangDian synchronization out of the
public API process.  It opens the configured SQLite file with ``mode=ro`` and
only exposes whitelisted table fields and aggregation operations.
"""

from __future__ import annotations

import os
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator

from .config import Settings, load_settings
from .db import InventoryDatabase

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# Public aliases are intentionally limited to the normalized business tables.
# raw_json is excluded from the public schema because it is large, unbounded,
# and may contain upstream fields that are not intended as a stable API.
DATASET_TABLES: Dict[str, str] = {
    "products": "products",
    "warehouses": "warehouse_master",
    "inventory_current": "inventory_current",
    "inventory_snapshots": "inventory_snapshots",
    "clearance_weekly_snapshots": "clearance_weekly_snapshots",
    "movements": "movements",
    "sales_lines": "sales_lines",
    "return_lines": "return_lines",
    "sync_runs": "sync_runs",
}

DATE_FIELDS = {
    "inventory_snapshots": "snapshot_date",
    "clearance_weekly_snapshots": "snapshot_date",
    "movements": "movement_date",
    "sales_lines": "sale_date",
    "return_lines": "return_date",
    "sync_runs": "sync_date",
}

AGGREGATIONS = {"count", "sum", "avg", "min", "max"}
OPERATORS = {"eq", "ne", "gt", "gte", "lt", "lte", "contains", "in", "is_null"}


class FilterItem(BaseModel):
    field: str
    op: str = "eq"
    value: Any = None

    @validator("field")
    def validate_field(cls, value: str) -> str:
        if not _IDENTIFIER.fullmatch(value):
            raise ValueError("field must be a valid column name")
        return value

    @validator("op")
    def validate_op(cls, value: str) -> str:
        value = value.lower()
        if value not in OPERATORS:
            raise ValueError(f"unsupported filter operator: {value}")
        return value


class MetricItem(BaseModel):
    field: str = "*"
    agg: str = "count"
    alias: Optional[str] = None

    @validator("field")
    def validate_field(cls, value: str) -> str:
        if value != "*" and not _IDENTIFIER.fullmatch(value):
            raise ValueError("field must be a valid column name or *")
        return value

    @validator("agg")
    def validate_agg(cls, value: str) -> str:
        value = value.lower()
        if value not in AGGREGATIONS:
            raise ValueError(f"unsupported aggregation: {value}")
        return value

    @validator("alias")
    def validate_alias(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not _IDENTIFIER.fullmatch(value):
            raise ValueError("alias must be a valid identifier")
        return value


class OrderItem(BaseModel):
    field: str
    direction: str = "desc"

    @validator("field")
    def validate_field(cls, value: str) -> str:
        if not _IDENTIFIER.fullmatch(value):
            raise ValueError("order field must be a valid identifier")
        return value

    @validator("direction")
    def validate_direction(cls, value: str) -> str:
        value = value.lower()
        if value not in {"asc", "desc"}:
            raise ValueError("direction must be asc or desc")
        return value


class QueryRequest(BaseModel):
    dataset: str = Field(..., description="数据集名称，见 /api/v1/datasets")
    fields: List[str] = Field(default_factory=list, description="明细字段；分组查询时为分组字段")
    filters: List[FilterItem] = Field(default_factory=list)
    group_by: List[str] = Field(default_factory=list)
    metrics: List[MetricItem] = Field(default_factory=list)
    order_by: List[OrderItem] = Field(default_factory=list)
    page: int = Field(1, ge=1, le=100000)
    page_size: int = Field(100, ge=1, le=1000)


class ReadOnlyDatabase(InventoryDatabase):
    """Type marker documenting that the API database must stay read-only."""

    def __init__(self, path: Path) -> None:
        super().__init__(path, read_only=True)


def _cors_origins() -> List[str]:
    raw = os.getenv("WDT_API_CORS_ORIGINS", "*").strip()
    return [item.strip() for item in raw.split(",") if item.strip()] or ["*"]


def _default_date_range(days: int = 30) -> Tuple[str, str]:
    end = date.today()
    return (end - timedelta(days=days - 1)).isoformat(), end.isoformat()


def _safe_identifier(value: str, kind: str = "field") -> str:
    if not _IDENTIFIER.fullmatch(value):
        raise HTTPException(status_code=400, detail=f"invalid {kind}: {value}")
    return value


def _schema(database: ReadOnlyDatabase, dataset: str) -> Tuple[str, List[str]]:
    table = DATASET_TABLES.get(dataset)
    if table is None:
        raise HTTPException(status_code=404, detail=f"unknown dataset: {dataset}")
    with database.connect() as connection:
        columns = [row["name"] for row in connection.execute(f'PRAGMA table_info("{table}")')]
    if not columns:
        raise HTTPException(status_code=500, detail=f"table is missing or empty in schema: {table}")
    return table, [column for column in columns if column != "raw_json"]


def _validate_columns(values: Sequence[str], columns: Sequence[str], label: str) -> List[str]:
    allowed = set(columns)
    result = []
    for value in values:
        _safe_identifier(value, label)
        if value not in allowed:
            raise HTTPException(status_code=400, detail=f"unknown {label}: {value}")
        if value not in result:
            result.append(value)
    return result


def _where_clause(filters: Sequence[FilterItem], columns: Sequence[str]) -> Tuple[str, List[Any]]:
    allowed = set(columns)
    clauses: List[str] = []
    params: List[Any] = []
    for item in filters:
        field = _safe_identifier(item.field)
        if field not in allowed:
            raise HTTPException(status_code=400, detail=f"unknown filter field: {field}")
        if item.op == "is_null":
            if item.value not in (None, "", True, False):
                raise HTTPException(status_code=400, detail="is_null filter value must be empty")
            clauses.append(f'"{field}" IS NULL')
        elif item.op == "in":
            if not isinstance(item.value, list) or not item.value:
                raise HTTPException(status_code=400, detail="in filter value must be a non-empty list")
            clauses.append(f'"{field}" IN ({",".join("?" for _ in item.value)})')
            params.extend(item.value)
        elif item.op == "contains":
            clauses.append(f'CAST("{field}" AS TEXT) LIKE ?')
            params.append(f"%{item.value}%")
        else:
            operator = {"eq": "=", "ne": "!=", "gt": ">", "gte": ">=", "lt": "<", "lte": "<="}[item.op]
            clauses.append(f'"{field}" {operator} ?')
            params.append(item.value)
    return (" WHERE " + " AND ".join(clauses)) if clauses else "", params


def _metric_expression(metric: MetricItem, columns: Sequence[str]) -> Tuple[str, str]:
    if metric.field != "*":
        _validate_columns([metric.field], columns, "metric field")
    expression = "COUNT(*)" if metric.agg == "count" and metric.field == "*" else f'{metric.agg.upper()}("{metric.field}")'
    alias = metric.alias or ("count" if metric.field == "*" else f"{metric.agg}_{metric.field}")
    return expression, alias


def _generic_query(database: ReadOnlyDatabase, request: QueryRequest) -> Dict[str, Any]:
    table, columns = _schema(database, request.dataset)
    fields = _validate_columns(request.fields, columns, "field")
    group_by = _validate_columns(request.group_by, columns, "group field")
    if fields and group_by and any(field not in group_by for field in fields):
        raise HTTPException(status_code=400, detail="fields in grouped query must be included in group_by")
    if request.metrics and not group_by and fields:
        raise HTTPException(status_code=400, detail="metrics without group_by cannot include detail fields")
    where, params = _where_clause(request.filters, columns)

    expressions: List[str] = []
    output_names: List[str] = []
    grouped = bool(group_by or request.metrics)
    if grouped:
        for field in group_by:
            expressions.append(f'"{field}"')
            output_names.append(field)
        for metric in request.metrics or [MetricItem(field="*", agg="count")]:
            expression, alias = _metric_expression(metric, columns)
            expressions.append(f'{expression} AS "{alias}"')
            output_names.append(alias)
        select_sql = ", ".join(expressions)
        group_sql = f' GROUP BY {", ".join(f"\"{field}\"" for field in group_by)}' if group_by else ""
        count_sql = f'SELECT COUNT(*) AS total FROM (SELECT {select_sql} FROM "{table}"{where}{group_sql}) grouped'
    else:
        selected = fields or columns
        select_sql = ", ".join(f'"{field}"' for field in selected)
        output_names = selected
        group_sql = ""
        count_sql = f'SELECT COUNT(*) AS total FROM "{table}"{where}'

    safe_order: List[str] = []
    for item in request.order_by:
        _safe_identifier(item.field, "order field")
        if item.field not in output_names:
            raise HTTPException(status_code=400, detail=f"order field is not in result: {item.field}")
        safe_order.append(f'"{item.field}" {item.direction.upper()}')
    order_sql = f' ORDER BY {", ".join(safe_order)}' if safe_order else ""
    offset = (request.page - 1) * request.page_size
    limit_sql = " LIMIT ? OFFSET ?"

    with database.connect() as connection:
        total = int(connection.execute(count_sql, params).fetchone()["total"])
        rows = connection.execute(
            f'SELECT {select_sql} FROM "{table}"{where}{group_sql}{order_sql}{limit_sql}',
            [*params, request.page_size, offset],
        ).fetchall()
    return {
        "dataset": request.dataset,
        "table": table,
        "fields": output_names,
        "page": request.page,
        "page_size": request.page_size,
        "total": total,
        "items": [dict(row) for row in rows],
    }


def _legacy_result(database: ReadOnlyDatabase, name: str, query: Dict[str, str]) -> Dict[str, Any]:
    start_default, end_default = _default_date_range()
    start = query.get("start", start_default)
    end = query.get("end", end_default)
    page = int(query.get("page", "1"))
    page_size = min(int(query.get("page_size", "100")), 1000)
    offset = (page - 1) * page_size
    search = query.get("search", "").strip()
    warehouse = query.get("warehouse", "").strip()
    if name == "inventory":
        return database.dashboard(start, end, search=search, warehouse_id=warehouse, stock_status=query.get("stock_status", ""), limit=page_size, offset=offset)
    if name == "sales":
        return database.warehouse_sku_sales(start, end, search=search, warehouse_id=warehouse, limit=page_size, offset=offset)
    if name == "shop-sales":
        return database.shop_sku_sales(start, end, search=search, shop_no=query.get("shop", ""), warehouse_id=warehouse, limit=page_size, offset=offset)
    if name == "inbound":
        inbound_type = query.get("inbound_type")
        return database.inbound_analysis(start, end, search=search, warehouse_id=warehouse, inbound_type=int(inbound_type) if inbound_type else None, limit=page_size, offset=offset)
    if name == "purchase-plan":
        return database.purchase_plan(start, end, search=search, warehouse_id=warehouse, limit=page_size, offset=offset, target_days=int(query.get("target_days", "30")))
    if name == "transfer-plan":
        return database.transfer_plan(start, end, search=search, warehouse_id=warehouse, limit=page_size, offset=offset)
    raise HTTPException(status_code=404, detail=f"unknown API resource: {name}")


def create_api(settings: Optional[Settings] = None) -> FastAPI:
    settings = settings or load_settings()
    database = ReadOnlyDatabase(settings.database_path)
    api = FastAPI(
        title="旺店通 SQLite 数据服务",
        description=(
            "只读访问现有旺店通 SQLite 数据库的 API。"
            "数据库写入和每日同步由外部任务负责，本服务不会修改数据库。"
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    api.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )
    api.state.settings = settings
    api.state.database = database

    @api.get("/api/v1/health", tags=["系统"])
    def health() -> Dict[str, Any]:
        try:
            with database.connect() as connection:
                connection.execute("SELECT 1").fetchone()
            return {"status": "ok", "database": "reachable", "read_only": True}
        except Exception as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @api.get("/api/v1/status", tags=["系统"])
    def status() -> Dict[str, Any]:
        last_sync = None
        with database.connect() as connection:
            row = connection.execute("SELECT * FROM sync_runs ORDER BY id DESC LIMIT 1").fetchone()
            if row:
                last_sync = dict(row)
        return {
            "status": "ok",
            "read_only": True,
            "database": settings.database_path.name,
            "environment": settings.environment,
            "last_sync": last_sync,
        }

    @api.get("/api/v1/datasets", tags=["元数据"])
    def datasets() -> Dict[str, Any]:
        result = []
        for name in DATASET_TABLES:
            table, columns = _schema(database, name)
            result.append({"dataset": name, "table": table, "date_field": DATE_FIELDS.get(name), "fields": columns})
        return {"items": result}

    @api.get("/api/v1/warehouses", tags=["元数据"])
    def warehouses() -> Dict[str, Any]:
        with database.connect() as connection:
            rows = connection.execute(
                'SELECT warehouse_id, warehouse_no, warehouse_name, warehouse_type, is_disabled, role, transfer_source_enabled FROM "warehouse_master" ORDER BY warehouse_name'
            ).fetchall()
        return {"total": len(rows), "items": [dict(row) for row in rows]}

    @api.post("/api/v1/query", tags=["通用查询"])
    def query(request: QueryRequest) -> Dict[str, Any]:
        """按数据集、字段、条件、分组和聚合进行安全只读查询。"""
        return _generic_query(database, request)

    @api.get("/api/v1/table/{dataset}", tags=["通用查询"])
    def table(
        dataset: str,
        page: int = Query(1, ge=1, le=100000),
        page_size: int = Query(100, ge=1, le=1000),
        field: Optional[List[str]] = Query(None),
        filter: Optional[List[str]] = Query(None, description="field:op:value，例如 warehouse_id:eq:1；可重复传入"),
    ) -> Dict[str, Any]:
        """简单 GET 查询，适合直接用 curl 或浏览器调用。"""
        filters: List[FilterItem] = []
        for expression in filter or []:
            try:
                field_name, op, raw_value = expression.split(":", 2)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="filter format must be field:op:value") from exc
            filters.append(FilterItem(field=field_name, op=op, value=raw_value))
        return _generic_query(database, QueryRequest(dataset=dataset, fields=field or [], filters=filters, page=page, page_size=page_size))

    def legacy_query(
        resource_name: str,
        start: Optional[str],
        end: Optional[str],
        page: int,
        page_size: int,
        search: str,
        warehouse: str,
        stock_status: str = "",
        shop: str = "",
        inbound_type: Optional[int] = None,
        target_days: int = 30,
    ) -> Dict[str, Any]:
        query = {
            "start": start or _default_date_range()[0],
            "end": end or _default_date_range()[1],
            "page": str(page),
            "page_size": str(page_size),
            "search": search,
            "warehouse": warehouse,
            "stock_status": stock_status,
            "shop": shop,
        }
        if inbound_type is not None:
            query["inbound_type"] = str(inbound_type)
        query["target_days"] = str(target_days)
        try:
            return _legacy_result(database, resource_name, query)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @api.get("/api/v1/inventory", tags=["业务查询"], summary="查询库存汇总")
    def inventory(
        start: Optional[str] = None, end: Optional[str] = None,
        page: int = Query(1, ge=1, le=100000), page_size: int = Query(100, ge=1, le=1000),
        search: str = "", warehouse: str = "", stock_status: str = "",
    ) -> Dict[str, Any]:
        return legacy_query("inventory", start, end, page, page_size, search, warehouse, stock_status=stock_status)

    @api.get("/api/v1/sales", tags=["业务查询"], summary="查询仓库 SKU 销量")
    def sales(
        start: Optional[str] = None, end: Optional[str] = None,
        page: int = Query(1, ge=1, le=100000), page_size: int = Query(100, ge=1, le=1000),
        search: str = "", warehouse: str = "",
    ) -> Dict[str, Any]:
        return legacy_query("sales", start, end, page, page_size, search, warehouse)

    @api.get("/api/v1/shop-sales", tags=["业务查询"], summary="查询店铺 SKU 销量")
    def shop_sales(
        start: Optional[str] = None, end: Optional[str] = None,
        page: int = Query(1, ge=1, le=100000), page_size: int = Query(100, ge=1, le=1000),
        search: str = "", warehouse: str = "", shop: str = "",
    ) -> Dict[str, Any]:
        return legacy_query("shop-sales", start, end, page, page_size, search, warehouse, shop=shop)

    @api.get("/api/v1/inbound", tags=["业务查询"], summary="查询入库分析")
    def inbound(
        start: Optional[str] = None, end: Optional[str] = None,
        page: int = Query(1, ge=1, le=100000), page_size: int = Query(100, ge=1, le=1000),
        search: str = "", warehouse: str = "", inbound_type: Optional[int] = None,
    ) -> Dict[str, Any]:
        return legacy_query("inbound", start, end, page, page_size, search, warehouse, inbound_type=inbound_type)

    @api.get("/api/v1/purchase-plan", tags=["业务查询"], summary="查询采购计划")
    def purchase_plan(
        start: Optional[str] = None, end: Optional[str] = None,
        page: int = Query(1, ge=1, le=100000), page_size: int = Query(100, ge=1, le=1000),
        search: str = "", warehouse: str = "", target_days: int = Query(30, ge=1, le=3650),
    ) -> Dict[str, Any]:
        return legacy_query("purchase-plan", start, end, page, page_size, search, warehouse, target_days=target_days)

    @api.get("/api/v1/transfer-plan", tags=["业务查询"], summary="查询调拨计划")
    def transfer_plan(
        start: Optional[str] = None, end: Optional[str] = None,
        page: int = Query(1, ge=1, le=100000), page_size: int = Query(100, ge=1, le=1000),
        search: str = "", warehouse: str = "",
    ) -> Dict[str, Any]:
        return legacy_query("transfer-plan", start, end, page, page_size, search, warehouse)

    @api.get("/api/v1/skus/{sku_no}", tags=["业务查询"])
    def sku_detail(sku_no: str, start: Optional[str] = None, end: Optional[str] = None) -> Dict[str, Any]:
        default_start, default_end = _default_date_range()
        result = database.sku_detail(sku_no, start or default_start, end or default_end)
        if result is None:
            raise HTTPException(status_code=404, detail="SKU not found")
        return result

    return api


app = create_api()


def main() -> None:
    import uvicorn

    uvicorn.run(
        "wangdian_inventory.api:app",
        host=os.getenv("WDT_API_HOST", "127.0.0.1"),
        port=int(os.getenv("WDT_API_PORT", "8000")),
        reload=os.getenv("WDT_API_RELOAD", "0") == "1",
    )


if __name__ == "__main__":
    main()
