"""Import curated product planning fields from a WPS/Excel workbook.

The workbook contains external-link formulas, so this importer deliberately
reads the cached displayed values and never tries to resolve the source files.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from wangdian_inventory.db import InventoryDatabase  # noqa: E402


MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
OFFICE_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS = {"m": MAIN_NS, "r": OFFICE_REL_NS}


def column_number(reference: str) -> int:
    letters = re.match(r"[A-Z]+", reference).group(0)
    number = 0
    for letter in letters:
        number = number * 26 + ord(letter) - ord("A") + 1
    return number


def shared_strings(archive: zipfile.ZipFile) -> List[str]:
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    return [
        "".join(node.text or "" for node in item.iter(f"{{{MAIN_NS}}}t"))
        for item in root.findall("m:si", NS)
    ]


def sheet_target(archive: zipfile.ZipFile, sheet_name: str) -> str:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    targets = {
        item.attrib["Id"]: item.attrib["Target"]
        for item in relationships.findall(f"{{{REL_NS}}}Relationship")
    }
    for sheet in workbook.find("m:sheets", NS):
        if sheet.attrib["name"] != sheet_name:
            continue
        rel_id = sheet.attrib[f"{{{OFFICE_REL_NS}}}id"]
        target = targets[rel_id]
        return target if target.startswith("xl/") else f"xl/{target}"
    raise ValueError(f"worksheet not found: {sheet_name}")


def read_rows(path: Path, sheet_name: str) -> List[Dict[str, str]]:
    with zipfile.ZipFile(path) as archive:
        strings = shared_strings(archive)
        worksheet = ET.fromstring(archive.read(sheet_target(archive, sheet_name)))
        rows = []
        for row in worksheet.findall(".//m:sheetData/m:row", NS):
            values: Dict[int, str] = {}
            for cell in row.findall("m:c", NS):
                value = cell.find("m:v", NS)
                cell_type = cell.attrib.get("t")
                if value is None:
                    text = ""
                elif cell_type == "s":
                    text = strings[int(value.text)]
                else:
                    text = value.text or ""
                values[column_number(cell.attrib["r"])] = text
            rows.append(values)

    header_index = next(
        index for index, row in enumerate(rows) if row.get(3, "") == "商家编码"
    )
    headers = rows[header_index]
    result = []
    for row in rows[header_index + 1 :]:
        sku_no = row.get(3, "").strip()
        if not sku_no:
            continue
        result.append(
            {
                "sku_no": sku_no,
                "category": row.get(7, "").strip(),
                "product_structure": row.get(8, "").strip(),
                "moq": row.get(9, "").strip(),
                "production_days": row.get(10, "").strip(),
            }
        )
    return result


def deduplicate(rows: Iterable[Dict[str, str]]) -> List[Dict[str, str]]:
    by_sku: Dict[str, Dict[str, str]] = {}
    for row in rows:
        existing = by_sku.get(row["sku_no"])
        if existing is None:
            by_sku[row["sku_no"]] = row
            continue
        for field in ("category", "product_structure", "moq", "production_days"):
            if existing[field] and row[field] and existing[field] != row[field]:
                raise ValueError(
                    f"conflicting {field} for SKU {row['sku_no']}: "
                    f"{existing[field]!r} vs {row[field]!r}"
                )
            existing[field] = existing[field] or row[field]
    return list(by_sku.values())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("/Users/tmt/Downloads/副本供应链智能体数据.xlsx"),
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=PROJECT_ROOT / "data" / "inventory_production.db",
    )
    parser.add_argument("--sheet", default="8.5")
    args = parser.parse_args()

    rows = deduplicate(read_rows(args.source, args.sheet))
    database = InventoryDatabase(args.database)
    result = database.upsert_product_metadata(
        rows,
        source=f"{args.source.name}#{args.sheet}",
    )
    result["source_rows"] = len(rows)
    result["configured_rows"] = sum(
        1 for row in rows if row["category"] and row["product_structure"] and row["production_days"]
    )
    with database.connect() as connection:
        result["product_status"] = dict(
            connection.execute(
                "SELECT metadata_status, COUNT(*) AS count FROM products GROUP BY metadata_status"
            ).fetchall()
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
