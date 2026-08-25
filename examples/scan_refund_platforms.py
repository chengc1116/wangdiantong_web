"""Scan refund-inbound orders and summarize platform/shop coverage.

Usage example:
  PYTHONPATH=src .venv/bin/python examples/scan_refund_platforms.py \
    --start 2026-07-01 --end 2026-07-30 --page-start 41 --page-end 60 \
    --output data/refund_scans/refunds_20260701_30_p041_060.json
"""

import argparse
import json
from collections import Counter
from datetime import datetime, time
from pathlib import Path
from typing import Any, Dict

from wangdian import WangdianClient
from wangdian_inventory.config import load_settings


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--page-start", type=int, required=True)
    parser.add_argument("--page-end", type=int, required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--shop-no", default="")
    parser.add_argument("--match-shop-no", action="append", default=[])
    args = parser.parse_args()
    settings = load_settings()
    if not settings.credentials_configured:
        raise SystemExit("WangDian credentials are not configured")
    start = datetime.combine(datetime.strptime(args.start, "%Y-%m-%d").date(), time.min)
    end = datetime.combine(datetime.strptime(args.end, "%Y-%m-%d").date(), time.max.replace(microsecond=0))
    rows = []
    page_counts = {}
    with WangdianClient(
        sid=settings.sid,
        app_key=settings.app_key,
        app_secret=settings.app_secret,
        environment=settings.environment,
        timeout=(10, 60),
        requests_per_minute=50,
    ) as client:
        for page_no in range(args.page_start, args.page_end + 1):
            request = {
                "start_time": start,
                "end_time": end,
                "page_no": page_no,
                "page_size": 100,
            }
            if args.shop_no:
                request["shop_no"] = args.shop_no
            response = client.call("stockin_order_query_refund", request)
            page_rows = response.get("stockin_list") or []
            if not isinstance(page_rows, list):
                raise ValueError("stockin_list is not a list")
            rows.extend(x for x in page_rows if isinstance(x, dict))
            page_counts[str(page_no)] = len(page_rows)
            if len(page_rows) < 100:
                break
    platforms = Counter(str(r.get("platform_id", "")) for r in rows)
    shops = Counter((str(r.get("platform_id", "")), str(r.get("shop_no", "")), str(r.get("shop_name", ""))) for r in rows)
    result: Dict[str, Any] = {
        "queried_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "environment": settings.environment,
        "endpoint": "stockin_order_query_refund",
        "request": {"start_time": start.strftime("%Y-%m-%d %H:%M:%S"), "end_time": end.strftime("%Y-%m-%d %H:%M:%S"), "page_start": args.page_start, "page_end": args.page_end, "page_size": 100, "shop_no": args.shop_no},
        "page_counts": page_counts,
        "records": len(rows),
        "platform_counts": dict(platforms),
        "shops": [{"platform_id": p, "shop_no": n, "shop_name": s, "count": c} for (p, n, s), c in shops.most_common()],
        "taobao_tmall_records": [r for r in rows if str(r.get("platform_id", "")) == "1"],
        "matched_shop_records": [r for r in rows if str(r.get("shop_no", "")) in set(args.match_shop_no)],
        "records_sample": rows[:5],
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output), "records": len(rows), "platform_counts": dict(platforms)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
