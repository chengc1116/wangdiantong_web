"""Query stock detail rows for one order and save the API result as JSON.

The API may ignore the source-order filter on some accounts, so the script
also filters ``src_order_no`` and ``warehouse_id`` locally before writing the
matching rows.
"""

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List

from wangdian import WangdianClient

from wangdian_inventory.config import load_settings


DEFAULT_START = "2026-07-31 00:00:00"
DEFAULT_END = "2026-07-31 23:59:59"
DEFAULT_ORDER = "JY2607314652"
DEFAULT_WAREHOUSE_ID = "39"
DEFAULT_SKUS = [
    "TJRP006F133JSCA0CC",  # 蓝色 7.5cm*4.6m
    "TJRP006F333JSCA0CC",  # 肤色 7.5cm*4.6m
]


def paginate(
    client: WangdianClient,
    parameters: Dict[str, Any],
    *,
    page_size: int = 100,
) -> Iterable[Dict[str, Any]]:
    page_no = 0
    while True:
        request = dict(parameters)
        request.update({"page_no": page_no, "page_size": page_size})
        response = client.call("stock_detail_report_query", request)
        rows = response.get("data") or []
        if not isinstance(rows, list):
            raise ValueError("stock_detail_report_query returned a non-list data field")
        for row in rows:
            if isinstance(row, dict):
                yield row
        if len(rows) < page_size:
            return
        page_no += 1


def main() -> None:
    parser = argparse.ArgumentParser(description="查询旺店通出入库明细并保存 JSON")
    parser.add_argument("--start", default=DEFAULT_START, help="开始时间")
    parser.add_argument("--end", default=DEFAULT_END, help="结束时间")
    parser.add_argument("--order", default=DEFAULT_ORDER, help="源单号")
    parser.add_argument("--warehouse-id", default=DEFAULT_WAREHOUSE_ID, help="仓库 ID")
    parser.add_argument(
        "--sku",
        action="append",
        dest="skus",
        help="SKU，可重复传入；默认查询蓝色和肤色两个 SKU",
    )
    parser.add_argument(
        "--output",
        default="tests/results/stock_detail_order_query.json",
        help="JSON 输出路径",
    )
    args = parser.parse_args()

    settings = load_settings()
    if not settings.credentials_configured:
        raise SystemExit(
            "未配置旺店通凭证，请填写 examples/wangdian_config.py "
            "或设置 WDT_SID/WDT_APP_KEY/WDT_APP_SECRET"
        )

    skus: List[str] = args.skus or list(DEFAULT_SKUS)
    query_results: List[Dict[str, Any]] = []
    matched: List[Dict[str, Any]] = []

    with WangdianClient(
        sid=settings.sid,
        app_key=settings.app_key,
        app_secret=settings.app_secret,
        environment=settings.environment,
        timeout=(10, 60),
        requests_per_minute=20,
    ) as client:
        for sku_no in skus:
            parameters = {
                "start_time": args.start,
                "end_time": args.end,
                "sku_no": sku_no,
            }
            rows = list(paginate(client, parameters))
            selected = [
                row
                for row in rows
                if str(row.get("src_order_no") or "") == args.order
                and str(row.get("warehouse_id") or "") == args.warehouse_id
            ]
            query_results.append(
                {
                    "sku_no": sku_no,
                    "request": parameters,
                    "records_fetched": len(rows),
                    "matching_records": len(selected),
                }
            )
            matched.extend(selected)

    output = {
        "queried_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "environment": settings.environment,
        "endpoint": "stock_detail_report_query",
        "filters": {
            "start_time": args.start,
            "end_time": args.end,
            "src_order_no": args.order,
            "warehouse_id": args.warehouse_id,
            "sku_no": skus,
        },
        "api_query_results": query_results,
        "matching_record_count": len(matched),
        "matching_out_num": sum(float(row.get("out_num") or 0) for row in matched),
        "matching_records": matched,
        "note": "订单号和仓库 ID 是在本地对 API 返回结果再次过滤的。",
    }
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "output": str(output_path),
        "matching_record_count": output["matching_record_count"],
        "matching_out_num": output["matching_out_num"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
