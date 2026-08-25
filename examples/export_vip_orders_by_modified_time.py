"""Export VIP raw orders using the API's modified-time filter."""

import argparse
import importlib.util
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from wangdian import WangdianClient


def load_local_config(config_path: Path):
    spec = importlib.util.spec_from_file_location("wangdian_local_config", config_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load configuration from {config_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export vip_api_trade_query.php results by modified time."
    )
    parser.add_argument("--start-time", required=True, help="YYYY-MM-DD HH:MM:SS")
    parser.add_argument("--end-time", required=True, help="YYYY-MM-DD HH:MM:SS")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--config", type=Path, default=Path("examples/wangdian_config.py"))
    args = parser.parse_args()

    for value in (args.start_time, args.end_time):
        datetime.strptime(value, "%Y-%m-%d %H:%M:%S")

    config = load_local_config(args.config)
    base_parameters = {
        "start_time": args.start_time,
        "end_time": args.end_time,
        "page_size": 100,
    }
    pages = []
    trade_list = []
    with WangdianClient(
        sid=config.SID,
        app_key=config.APP_KEY,
        app_secret=config.APP_SECRET,
        environment=config.ENVIRONMENT,
        requests_per_minute=50,
    ) as client:
        page_no = 0
        while True:
            result = client.call(
                "vip_api_trade_query",
                {**base_parameters, "page_no": page_no},
            )
            page_trades = result.get("trade_list") or []
            pages.append({"page_no": page_no, "response": result})
            trade_list.extend(page_trades)
            total_count = int(result.get("total_count") or 0)
            if not page_trades or len(trade_list) >= total_count:
                break
            page_no += 1

    export = {
        "exported_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "endpoint": "vip_api_trade_query.php",
        "query_basis": "modified (VIP API order last-modified time)",
        "request_parameters": base_parameters,
        "returned_trade_count": len(trade_list),
        "pages": pages,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(export, ensure_ascii=False, indent=2), encoding="utf-8")
    os.chmod(args.output, 0o600)
    print(f"Exported {len(trade_list)} orders to {args.output}")


if __name__ == "__main__":
    main()
