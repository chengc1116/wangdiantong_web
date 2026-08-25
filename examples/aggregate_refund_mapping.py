"""Build a compact audit report from refund scan batches."""

import json
from collections import Counter
from pathlib import Path


def main() -> None:
    root = Path("data/refund_scans")
    master = json.loads(Path("tests/results/shops.json").read_text(encoding="utf-8"))
    shop_master = {str(x.get("shop_no", "")): x for x in master}
    report = {"endpoint": "stockin_order_query_refund", "windows": []}
    for prefix, label in [
        ("refunds_20260701_30_", "2026-07-01..2026-07-30"),
        ("refunds_20260731_0816_", "2026-07-31..2026-08-16"),
    ]:
        files = sorted(root.glob(prefix + "*.json"))
        platform_counts = Counter()
        records = 0
        shops = Counter()
        for path in files:
            data = json.loads(path.read_text(encoding="utf-8"))
            records += int(data["records"])
            platform_counts.update(data["platform_counts"])
            for shop in data["shops"]:
                shops[(shop["shop_no"], shop["shop_name"], shop["platform_id"])] += int(shop["count"])
        mapped = []
        mapped_files = sorted(root.glob("mapped_" + ("20260701_30_" if label.startswith("2026-07-01") else "never_") + "*.json"))
        if label.startswith("2026-07-01"):
            mapped_files = sorted(root.glob("mapped_20260701_30_*.json"))
        for path in mapped_files:
            mapped.extend(json.loads(path.read_text(encoding="utf-8")).get("matched_shop_records", []))
        mapped_out = []
        for row in mapped:
            master_row = shop_master.get(str(row.get("shop_no", "")), {})
            mapped_out.append({
                "trade_no": row.get("trade_no", ""),
                "src_order_no": row.get("src_order_no", ""),
                "stockin_id": row.get("stockin_id", ""),
                "order_no": row.get("order_no", ""),
                "stockin_time": row.get("stockin_time", ""),
                "warehouse_id": row.get("warehouse_id", ""),
                "warehouse_name": row.get("warehouse_name", ""),
                "shop_id": row.get("shop_id", ""),
                "shop_no": row.get("shop_no", ""),
                "shop_name": row.get("shop_name", ""),
                "returned_platform_id": row.get("platform_id", ""),
                "master_platform_id": master_row.get("platform_id"),
                "master_sub_platform_id": master_row.get("sub_platform_id"),
                "details_list": row.get("details_list", []),
            })
        report["windows"].append({
            "window": label,
            "records": records,
            "platform_counts": dict(platform_counts),
            "returned_platform_1_count": int(platform_counts.get("1", 0)),
            "taobao_shop_mapping_count": len(mapped_out),
            "taobao_shop_mapping_records": mapped_out,
            "shop_summary": [{"shop_no": no, "shop_name": name, "returned_platform_id": platform, "count": count, "master_platform_id": shop_master.get(no, {}).get("platform_id")} for (no, name, platform), count in shops.most_common()],
        })
    output = root / "refund_platform_audit_20260701_0816.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output), "windows": [{"window": x["window"], "records": x["records"], "platform_1": x["returned_platform_1_count"], "taobao_mapping": x["taobao_shop_mapping_count"]} for x in report["windows"]]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
