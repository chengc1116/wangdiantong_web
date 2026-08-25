"""Reconcile sampled refund-inbound rows to their original outbound warehouse.

The refund API's ``trade_no`` is matched to sales ``src_order_no`` together
with the returned SKU.  The refund API ``src_order_no`` (usually a TK number)
is deliberately not used as the sales key.
"""

import json
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path


DB = Path("data/inventory_production.db")
ROOT = Path("data/refund_scans")
OUT = ROOT / "return_to_outbound_warehouse_20260701_0816.json"


def main() -> None:
    master = json.loads(Path("tests/results/shops.json").read_text(encoding="utf-8"))
    rows = []
    for path in sorted(ROOT.glob("mapped_*.json")):
        rows.extend(json.loads(path.read_text(encoding="utf-8")).get("matched_shop_records", []))

    connection = sqlite3.connect(DB)
    connection.row_factory = sqlite3.Row
    sales = defaultdict(list)
    query = """
        SELECT s.src_order_no, s.sku_no, s.quantity,
               s.warehouse_id,
               COALESCE(NULLIF(s.warehouse_name,''), wm.warehouse_name, s.warehouse_id) warehouse_name
        FROM sales_lines s
        LEFT JOIN warehouse_master wm ON wm.warehouse_id=s.warehouse_id
        WHERE s.src_order_no=? AND s.sku_no=?
    """
    details = []
    for order in rows:
        trade_no = str(order.get("trade_no") or "")
        for detail in order.get("details_list") or []:
            sku = str(detail.get("spec_no") or "")
            returned_qty = float(detail.get("num") or 0)
            matches = [dict(x) for x in connection.execute(query, (trade_no, sku)).fetchall()]
            warehouse_qty = Counter()
            for match in matches:
                warehouse_qty[(str(match["warehouse_id"]), str(match["warehouse_name"]))] += float(match["quantity"] or 0)
            if not matches:
                status = "未匹配原出库"
            elif len(warehouse_qty) == 1:
                status = "已匹配原出库仓"
            else:
                status = "匹配到多个出库仓"
            details.append({
                "trade_no": trade_no,
                "refund_source_order_no": order.get("src_order_no", ""),
                "return_inbound_order_no": order.get("order_no", ""),
                "return_stockin_id": order.get("stockin_id", ""),
                "return_time": order.get("stockin_time", ""),
                "return_warehouse_id": order.get("warehouse_id", ""),
                "return_warehouse_name": order.get("warehouse_name", ""),
                "shop_no": order.get("shop_no", ""),
                "shop_name": order.get("shop_name", ""),
                "sku_no": sku,
                "goods_name": detail.get("goods_name", ""),
                "spec_name": detail.get("spec_name", ""),
                "returned_qty": returned_qty,
                "match_status": status,
                "original_outbound_warehouses": [
                    {"warehouse_id": warehouse_id, "warehouse_name": warehouse_name, "outbound_qty": qty}
                    for (warehouse_id, warehouse_name), qty in warehouse_qty.items()
                ],
            })
    connection.close()
    by_warehouse = Counter()
    for row in details:
        if row["match_status"] == "已匹配原出库仓":
            target = row["original_outbound_warehouses"][0]
            by_warehouse[(target["warehouse_id"], target["warehouse_name"])] += row["returned_qty"]
    result = {
        "method": "return.trade_no = sales.src_order_no AND return_detail.spec_no = sales.sku_no",
        "source_files": len(list(ROOT.glob("mapped_*.json"))),
        "return_detail_count": len(details),
        "match_status_counts": dict(Counter(row["match_status"] for row in details)),
        "returned_qty_by_original_outbound_warehouse": [
            {"warehouse_id": warehouse_id, "warehouse_name": warehouse_name, "returned_qty": qty}
            for (warehouse_id, warehouse_name), qty in by_warehouse.most_common()
        ],
        "details": details,
        "caveat": "This is a reconciliation of the refund rows captured from the API, not a complete ERP return total. A trade/SKU shipped from multiple warehouses cannot be assigned uniquely without a detail-level outbound link.",
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(OUT), "return_detail_count": len(details), "match_status_counts": result["match_status_counts"], "warehouse_summary": result["returned_qty_by_original_outbound_warehouse"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
