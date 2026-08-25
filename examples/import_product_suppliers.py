"""Backfill product suppliers from a saved WangDian goods_query response."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from wangdian_inventory.db import InventoryDatabase  # noqa: E402


def supplier_specs(payload: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    for goods in payload.get("goods_list") or []:
        if not isinstance(goods, dict):
            continue
        for spec in goods.get("spec_list") or []:
            if isinstance(spec, dict):
                yield spec


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        default=PROJECT_ROOT / "tests/results/goods_query_category_structure_20260805.json",
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=PROJECT_ROOT / "data/inventory_production.db",
    )
    args = parser.parse_args()

    with args.source.open(encoding="utf-8") as source:
        payload = json.load(source)
    specs = list(supplier_specs(payload))
    database = InventoryDatabase(args.database)
    result = database.upsert_product_suppliers(specs)
    result.update({
        "source": str(args.source),
        "source_specs": len(specs),
        "source_goods": len(payload.get("goods_list") or []),
    })
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
