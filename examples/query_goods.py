"""Query WangDian goods_query and save raw plus inspectable JSON files.

Examples (run from the project root)::

    .venv/bin/python examples/query_goods.py --sku 9825172526-2-JM
    .venv/bin/python examples/query_goods.py --sku SKU-1 --sku SKU-2

The script reads credentials from ``examples/wangdian_config.py`` or the
``WDT_SID``, ``WDT_APP_KEY``, ``WDT_APP_SECRET`` and ``WDT_ENV`` environment
variables. It never writes credentials into the output files.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from wangdian import WangdianClient  # noqa: E402
from wangdian_inventory.config import load_settings  # noqa: E402


DEFAULT_SKU = "9825172526-2-JM"
PROP_KEYS = [f"prop{index}" for index in range(1, 11)]


def _non_empty(value: Any) -> bool:
    return value not in (None, "", [], {})


def _non_empty_fields(item: Mapping[str, Any]) -> Dict[str, Any]:
    """Keep scalar/non-empty fields while avoiding duplicated nested payloads."""
    result: Dict[str, Any] = {}
    for key, value in item.items():
        if _non_empty(value) and not isinstance(value, (list, dict)):
            result[key] = value
    return result


def _prop_fields(item: Mapping[str, Any]) -> Dict[str, Any]:
    return {key: item.get(key) for key in PROP_KEYS if _non_empty(item.get(key))}


def _custom_fields(item: Mapping[str, Any]) -> Dict[str, Any]:
    """Collect fields likely to carry custom attributes without guessing prop order."""
    keywords = ("custom", "property", "attribute", "自定义", "产线", "产能")
    result: Dict[str, Any] = {}
    for key, value in item.items():
        if _non_empty(value) and any(word in str(key).lower() for word in keywords):
            result[key] = value
    return result


def _iter_goods(response: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
    goods_list = response.get("goods_list") or []
    if not isinstance(goods_list, list):
        raise ValueError("goods_query returned a non-list goods_list field")
    return (item for item in goods_list if isinstance(item, dict))


def build_summary(response: Mapping[str, Any], request: Mapping[str, Any], environment: str) -> Dict[str, Any]:
    goods_summary: List[Dict[str, Any]] = []
    for goods in _iter_goods(response):
        specs: List[Dict[str, Any]] = []
        raw_specs = goods.get("spec_list") or []
        if not isinstance(raw_specs, list):
            raw_specs = []
        for spec in raw_specs:
            if not isinstance(spec, dict):
                continue
            specs.append(
                {
                    "spec_no": spec.get("spec_no"),
                    "spec_name": spec.get("spec_name"),
                    "prop_fields": _prop_fields(spec),
                    "custom_fields": _custom_fields(spec),
                    "non_empty_fields": _non_empty_fields(spec),
                }
            )
        goods_summary.append(
            {
                "goods_no": goods.get("goods_no"),
                "goods_name": goods.get("goods_name"),
                "short_name": goods.get("short_name"),
                "category_name": goods.get("category_name"),
                "prop_fields": _prop_fields(goods),
                "custom_fields": _custom_fields(goods),
                "non_empty_fields": _non_empty_fields(goods),
                "spec_count": len(specs),
                "spec_list": specs,
            }
        )
    return {
        "queried_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "environment": environment,
        "endpoint": "goods_query",
        "request": dict(request),
        "response_code": response.get("code"),
        "total_count": response.get("total_count"),
        "goods_count": len(goods_summary),
        "goods_list": goods_summary,
        "notes": [
            "prop_fields reports non-empty prop1..prop10 values only.",
            "custom_fields reports keys whose names suggest custom/property/attribute fields; it does not infer a prop number as 产线 or 产能.",
            "non_empty_fields preserves all scalar non-empty fields for inspection.",
        ],
    }


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="查询旺店通货品并保存原始/整理 JSON")
    parser.add_argument(
        "--sku",
        action="append",
        dest="skus",
        help=f"SKU，可重复传入；默认查询 {DEFAULT_SKU}",
    )
    parser.add_argument("--page-size", type=int, default=100, help="API page_size，默认 100")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "goods_query_live",
        help="输出目录，默认 data/goods_query_live",
    )
    args = parser.parse_args()
    if args.page_size < 1 or args.page_size > 1000:
        parser.error("--page-size 必须在 1 到 1000 之间")

    settings = load_settings()
    if not settings.credentials_configured:
        print("未配置旺店通凭证，请填写 examples/wangdian_config.py 或设置 WDT_SID/WDT_APP_KEY/WDT_APP_SECRET", file=sys.stderr)
        return 2

    skus = [sku.strip() for sku in (args.skus or [DEFAULT_SKU]) if sku and sku.strip()]
    if not skus:
        parser.error("至少需要一个非空 --sku")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = args.output_dir / f"goods_query_{stamp}"

    requests: List[Dict[str, Any]] = [
        {"spec_no": sku, "page_no": 0, "page_size": args.page_size}
        for sku in skus
    ]
    responses: List[Dict[str, Any]] = []
    try:
        with WangdianClient(
            sid=settings.sid,
            app_key=settings.app_key,
            app_secret=settings.app_secret,
            environment=settings.environment,
            timeout=(10, 60),
            requests_per_minute=20,
        ) as client:
            for sku, request in zip(skus, requests):
                responses.append({
                    "sku": sku,
                    "request": request,
                    "response": client.call("goods_query", request),
                })
    except Exception as exc:  # Keep a machine-readable diagnostic for network/API failures.
        error = {
            "queried_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "environment": settings.environment,
            "endpoint": "goods_query",
            "requests": requests,
            "completed_requests": responses,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "next_step": "把这个 error.json 发回；如果是 DNS/网络错误，请在可访问旺店通的机器执行。",
        }
        error_path = prefix.with_name(prefix.name + "_error.json")
        _write_json(error_path, error)
        print(f"请求失败，诊断已保存：{error_path}", file=sys.stderr)
        print(json.dumps(error, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1

    all_goods: List[Dict[str, Any]] = []
    for item in responses:
        payload = item["response"]
        all_goods.extend(
            goods for goods in (payload.get("goods_list") or []) if isinstance(goods, dict)
        )
    combined_response: Dict[str, Any] = {
        "code": 0,
        "total_count": len(all_goods),
        "goods_list": all_goods,
    }
    raw_payload = {
        "queried_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "environment": settings.environment,
        "endpoint": "goods_query",
        "requests": requests,
        "responses": responses,
        "combined_goods_count": len(all_goods),
        "goods_list": all_goods,
    }
    raw_path = prefix.with_name(prefix.name + "_raw.json")
    summary_path = prefix.with_name(prefix.name + "_summary.json")
    _write_json(raw_path, raw_payload)
    _write_json(summary_path, build_summary(combined_response, {"spec_no": skus}, settings.environment))
    print(f"原始回包：{raw_path}")
    print(f"整理结果：{summary_path}")
    print(f"货品数：{len(all_goods)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
