"""Compare one day's generic stock-in API with the refund stock-in API.

The generic endpoint is queried without ``order_type`` so the returned
``src_order_type`` values reveal whether it includes customer return orders.
"""

import argparse
import json
from collections import Counter
from datetime import datetime, time
from pathlib import Path
from typing import Any, Dict, Iterable, List

from wangdian import WangdianClient
from wangdian_inventory.config import load_settings


def paginate(client: WangdianClient, endpoint: str, params: Dict[str, Any], key: str) -> Iterable[Dict[str, Any]]:
    page = 0
    while True:
        payload = {**params, "page_no": page, "page_size": 100}
        response = client.call(endpoint, payload)
        entries = response.get(key) or []
        if not isinstance(entries, list):
            raise ValueError(f"{endpoint} returned non-list {key}")
        yield from (entry for entry in entries if isinstance(entry, dict))
        if len(entries) < 100:
            return
        page += 1


def get_stockin_no(row: Dict[str, Any]) -> str:
    return str(row.get("stockin_no") or row.get("order_no") or "")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default="2026-08-18")
    parser.add_argument("--output", default="data/refund_scans/stockin_api_comparison_20260818.json")
    parser.add_argument(
        "--shops-file",
        default="tests/results/shops.json",
        help="shop_query_Y result used to identify Taobao/Tmall shops",
    )
    args = parser.parse_args()
    day = datetime.strptime(args.date, "%Y-%m-%d").date()
    params = {
        "start_time": datetime.combine(day, time.min),
        "end_time": datetime.combine(day, time.max.replace(microsecond=0)),
    }
    settings = load_settings()
    with WangdianClient(
        sid=settings.sid, app_key=settings.app_key, app_secret=settings.app_secret,
        environment=settings.environment, timeout=(10, 60), requests_per_minute=30,
    ) as client:
        generic = list(paginate(client, "stockin_order_query", params, "stockin_list"))
        refunds = list(paginate(client, "stockin_order_query_refund", params, "stockin_list"))
    generic_by_no = {get_stockin_no(row): row for row in generic if get_stockin_no(row)}
    refund_by_no = {get_stockin_no(row): row for row in refunds if get_stockin_no(row)}
    common = sorted(set(generic_by_no) & set(refund_by_no))
    shops_master = []
    shops_path = Path(args.shops_file)
    if shops_path.exists():
        try:
            shops_master = json.loads(shops_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            shops_master = []
    taobao_shop_nos = {
        str(shop.get("shop_no") or "")
        for shop in shops_master
        if str(shop.get("platform_id") or "") == "1"
    }
    taobao_refunds = [
        row for row in refunds
        if str(row.get("platform_id") or "") == "1"
        or str(row.get("shop_no") or "") in taobao_shop_nos
    ]
    taobao_refund_only = [
        row for row in taobao_refunds if get_stockin_no(row) not in generic_by_no
    ]
    taobao_common = [
        row for row in taobao_refunds if get_stockin_no(row) in generic_by_no
    ]
    generic_return_like = [row for row in generic if str(row.get("src_order_no") or "").startswith(("RT", "TK"))]
    generic_rows = []
    for row in generic_return_like:
        stockin_no = get_stockin_no(row)
        generic_rows.append({
            "stockin_no": stockin_no,
            "src_order_no": row.get("src_order_no", ""),
            "src_order_type": row.get("src_order_type"),
            "src_order_type_name": row.get("src_order_type_name", ""),
            "warehouse_id": row.get("warehouse_id", ""),
            "warehouse_name": row.get("warehouse_name", ""),
            "refund_no": row.get("refund_no", ""),
            "refund_type": row.get("refund_type"),
            "refund_reason": row.get("refund_reason"),
            "refund_logistics_no": row.get("refund_logistics_no", ""),
            "in_refund_endpoint": stockin_no in refund_by_no,
            "raw": row,
        })
    result = {
        "date": args.date,
        "requests": {"start_time": params["start_time"].strftime("%F %T"), "end_time": params["end_time"].strftime("%F %T")},
        "generic": {
            "endpoint": "stockin_order_query",
            "record_count": len(generic),
            "src_order_type_counts": dict(Counter(str(x.get("src_order_type", "")) for x in generic)),
            "field_names": sorted({key for row in generic for key in row}),
            "return_like_count": len(generic_return_like),
            "return_like_records": generic_rows,
        },
        "refund": {
            "endpoint": "stockin_order_query_refund",
            "record_count": len(refunds),
            "field_names": sorted({key for row in refunds for key in row}),
            "stockin_nos": sorted(refund_by_no),
            "sample": refunds[:3],
            "taobao_shop_nos_from_shop_master": sorted(taobao_shop_nos),
            "taobao_tmall_record_count": len(taobao_refunds),
            "taobao_tmall_records": taobao_refunds,
        },
        "comparison": {
            "common_stockin_count": len(common),
            "common_stockin_nos": common,
            "generic_only_stockin_count": len(set(generic_by_no) - set(refund_by_no)),
            "refund_only_stockin_count": len(set(refund_by_no) - set(generic_by_no)),
            "taobao_common_stockin_count": len(taobao_common),
            "taobao_refund_only_stockin_count": len(taobao_refund_only),
            "taobao_refund_only_records": taobao_refund_only,
            "generic_return_records_have_shop_fields": any(
                key in generic_return_like[0] for key in ("shop_id", "shop_no", "shop_name", "platform_id")
            ) if generic_return_like else False,
            "common_field_names": sorted(set().union(*(set(x) for x in generic)).intersection(set().union(*(set(x) for x in refunds)))) if generic and refunds else [],
            "generic_only_field_names": sorted(set().union(*(set(x) for x in generic)) - set().union(*(set(x) for x in refunds))) if generic else [],
            "refund_only_field_names": sorted(set().union(*(set(x) for x in refunds)) - set().union(*(set(x) for x in generic))) if refunds else [],
        },
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "output": str(output), "generic": len(generic), "generic_return_like": len(generic_return_like),
        "refund": len(refunds), "common_stockin": len(common),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
