"""Export clearance inventory rows whose cost fields are missing."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / "data" / "inventory_production.db"
OUTPUT = ROOT / "data" / "clearance_missing_cost.json"


def main() -> None:
    query = """
        SELECT i.sku_no,
               COALESCE(p.short_name, '') AS short_name,
               COALESCE(p.goods_name, '') AS goods_name,
               COALESCE(p.spec_name, '') AS spec_name,
               COALESCE(p.goods_no, '') AS goods_no,
               COALESCE(p.category, '') AS category,
               COALESCE(p.product_structure, '') AS product_structure,
               COALESCE(p.supplier_name, '') AS supplier_name,
               i.warehouse_id,
               COALESCE(NULLIF(i.warehouse_name, ''), wm.warehouse_name,
                        i.warehouse_no, '仓库 ' || i.warehouse_id) AS warehouse_name,
               i.stock_num,
               i.available_num,
               i.avg_cost_price,
               i.cost_price,
               i.synced_at
        FROM inventory_current i
        JOIN products p ON p.sku_no = i.sku_no
        LEFT JOIN warehouse_master wm ON wm.warehouse_id = i.warehouse_id
        WHERE p.product_structure = '清仓款'
          AND COALESCE(wm.is_disabled, 0) = 0
          AND COALESCE(wm.role, 'sales') = 'sales'
          AND i.stock_num > 0
          AND COALESCE(i.avg_cost_price, 0) <= 0
          AND COALESCE(i.cost_price, 0) <= 0
        ORDER BY i.stock_num DESC, p.short_name, i.sku_no
    """
    with sqlite3.connect(DATABASE) as connection:
        connection.row_factory = sqlite3.Row
        rows = [dict(row) for row in connection.execute(query)]
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "criteria": {
            "product_structure": "清仓款",
            "warehouse_role": "sales",
            "stock_num": "> 0",
            "avg_cost_price": "<= 0",
            "cost_price": "<= 0",
        },
        "count": len(rows),
        "items": rows,
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(rows)} rows to {OUTPUT}")


if __name__ == "__main__":
    main()
