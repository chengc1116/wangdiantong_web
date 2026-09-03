import sqlite3
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from wangdian_inventory.api import create_api
from wangdian_inventory.config import Settings
from wangdian_inventory.db import InventoryDatabase


class ApiTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "inventory.db"
        writable = InventoryDatabase(self.path)
        with writable.connect() as conn:
            conn.executemany(
                "INSERT INTO products (sku_no, goods_no, goods_name, short_name, spec_name, barcode, unit_name, supplier_id, supplier_no, supplier_name, supplier_updated_at, retail_price, wholesale_price, purchase_price, category, product_structure, moq, production_days, production_line, production_capacity, spec_remark, goods_remark, erp_price, metadata_status, metadata_source, metadata_updated_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    ("SKU-1", "G-1", "商品一", "一", "标准", "", "件", "", "", "供应商", "", 10, 8, 5, "护具", "成品", 1, 10, "", "", "", "", None, "", "", "", "2026-09-01"),
                    ("SKU-2", "G-2", "商品二", "二", "标准", "", "件", "", "", "供应商", "", 20, 16, 9, "配件", "成品", 1, 30, "", "", "", "", None, "", "", "", "2026-09-01"),
                ],
            )
            conn.executemany(
                "INSERT INTO inventory_current (sku_no, warehouse_id, warehouse_no, warehouse_name, stock_num, available_num, cost_price, avg_cost_price, purchase_in_transit_num, modified, synced_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    ("SKU-1", "W-1", "001", "主仓", 10, 8, 5, 5, 2, "", "2026-09-01"),
                    ("SKU-2", "W-1", "001", "主仓", 4, 4, 9, 9, 0, "", "2026-09-01"),
                    ("SKU-1", "W-2", "002", "门店仓", 7, 7, 5, 5, 0, "", "2026-09-01"),
                ],
            )
            conn.executemany(
                "INSERT INTO sales_lines (sale_key, sale_date, consign_time, sku_no, warehouse_id, warehouse_no, warehouse_name, shop_id, shop_no, shop_name, quantity, paid_amount, share_amount, retail_price, sell_price, cost_price, modified) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    ("S-1", "2026-09-01", "", "SKU-1", "W-1", "001", "主仓", "SH-1", "SHOP-1", "旗舰店", 3, 30, 30, 10, 10, 5, ""),
                    ("S-2", "2026-09-02", "", "SKU-1", "W-2", "002", "门店仓", "SH-2", "SHOP-2", "分店", 2, 20, 20, 10, 10, 5, ""),
                    ("S-3", "2026-09-02", "", "SKU-2", "W-1", "001", "主仓", "SH-1", "SHOP-1", "旗舰店", 1, 20, 20, 20, 20, 9, ""),
                ],
            )
        settings = Settings("", "", "", "test", self.path, True)
        self.client = TestClient(create_api(settings))

    def tearDown(self):
        self.tmp.cleanup()

    def test_health_status_and_metadata(self):
        response = self.client.get("/api/v1/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["read_only"], True)

        response = self.client.get("/api/v1/status")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["database"], "inventory.db")
        self.assertNotIn(str(self.path), response.text)

        response = self.client.get("/api/v1/datasets")
        self.assertEqual(response.status_code, 200)
        datasets = {item["dataset"]: item for item in response.json()["items"]}
        self.assertIn("inventory_current", datasets)
        self.assertNotIn("raw_json", datasets["products"]["fields"])

    def test_detail_filter_and_pagination(self):
        response = self.client.post(
            "/api/v1/query",
            json={
                "dataset": "inventory_current",
                "fields": ["sku_no", "warehouse_name", "available_num"],
                "filters": [{"field": "available_num", "op": "gte", "value": 7}],
                "order_by": [{"field": "available_num", "direction": "desc"}],
                "page": 1,
                "page_size": 2,
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["total"], 2)
        self.assertEqual(len(body["items"]), 2)
        self.assertEqual(body["items"][0]["available_num"], 8)

        response = self.client.post(
            "/api/v1/query",
            json={
                "dataset": "inventory_current",
                "fields": ["sku_no"],
                "page": 2,
                "page_size": 2,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["items"]), 1)

    def test_grouped_aggregation_and_in_filter(self):
        response = self.client.post(
            "/api/v1/query",
            json={
                "dataset": "sales_lines",
                "filters": [{"field": "sku_no", "op": "in", "value": ["SKU-1", "SKU-2"]}],
                "group_by": ["warehouse_name"],
                "metrics": [
                    {"field": "quantity", "agg": "sum", "alias": "sales_qty"},
                    {"field": "sale_key", "agg": "count", "alias": "line_count"},
                ],
                "order_by": [{"field": "sales_qty", "direction": "desc"}],
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["total"], 2)
        self.assertEqual(body["items"][0]["warehouse_name"], "主仓")
        self.assertEqual(body["items"][0]["sales_qty"], 4)
        self.assertEqual(body["items"][0]["line_count"], 2)

    def test_invalid_column_and_group_request_are_rejected(self):
        response = self.client.post(
            "/api/v1/query",
            json={"dataset": "products", "fields": ["does_not_exist"]},
        )
        self.assertEqual(response.status_code, 400)

        response = self.client.post(
            "/api/v1/query",
            json={
                "dataset": "products",
                "fields": ["goods_name"],
                "metrics": [{"field": "sku_no", "agg": "count"}],
            },
        )
        self.assertEqual(response.status_code, 400)

        response = self.client.get("/api/v1/table/products?filter=sku_no:eq:SKU-1&field=sku_no")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["items"][0]["sku_no"], "SKU-1")

    def test_database_connection_is_read_only(self):
        database = create_api(Settings("", "", "", "test", self.path, True)).state.database
        with self.assertRaises(sqlite3.OperationalError):
            with database.connect() as conn:
                conn.execute("CREATE TABLE should_not_exist (id INTEGER)")


if __name__ == "__main__":
    unittest.main()
