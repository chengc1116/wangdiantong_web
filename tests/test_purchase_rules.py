from datetime import date, timedelta
from pathlib import Path
import sys
import tempfile
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from wangdian_inventory.db import (  # noqa: E402
    InventoryDatabase,
    _purchase_category,
    _target_week_multiplier,
    _trend_purchase_multiplier,
)


class PurchaseRuleHelperTests(unittest.TestCase):
    def test_purchase_category_mapping(self):
        cases = {
            "护具/护腕": "护腕",
            "护具/护膝": "护膝",
            "护具/护踝": "护踝",
            "护具/护腰": "护腰",
            "护具/髌骨带": "其他",
            "睡眠/眼罩": "其他",
            "": "其他",
        }
        for source, expected in cases.items():
            with self.subTest(source=source):
                self.assertEqual(_purchase_category(source), expected)

    def test_trend_purchase_multiplier_boundaries(self):
        cases = [
            (None, 1.0),
            (0.49, 0.5),
            (0.5, 0.6),
            (0.79, 0.6),
            (0.8, 1.0),
            (1.19, 1.0),
            (1.2, 1.2),
            (1.79, 1.2),
            (1.8, 1.4),
        ]
        for coefficient, expected in cases:
            with self.subTest(coefficient=coefficient):
                self.assertEqual(_trend_purchase_multiplier(coefficient), expected)

    def test_target_week_multiplier(self):
        cases = [(None, None), (15, 4.0), (20, 4.0), (25, 7.0), (30, 8.0)]
        for production_days, expected in cases:
            with self.subTest(production_days=production_days):
                self.assertEqual(_target_week_multiplier(production_days), expected)


class PurchasePlanWorkbookRuleTests(unittest.TestCase):
    def test_excel_daily_weight_weekly_formula_and_5_20_dates(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database = InventoryDatabase(Path(temp_dir) / "inventory.db")
            end = date(2026, 8, 27)
            with database.connect() as connection:
                connection.execute(
                    """
                    INSERT INTO warehouse_master (
                        warehouse_id, warehouse_no, warehouse_name, is_disabled, role
                    ) VALUES ('1', 'MAIN', '主仓库（新）', 0, 'sales')
                    """
                )
                connection.execute(
                    """
                    INSERT INTO products (
                        sku_no, goods_name, category, product_structure, production_days,
                        supplier_name, moq, metadata_status, updated_at
                    ) VALUES (
                        'TEST-SKU', '测试护腕', '护具/护腕', '基础款', 25,
                        '铠博', 100, '已配置', '2026-08-27T00:00:00'
                    )
                    """
                )
                connection.execute(
                    """
                    INSERT INTO inventory_current (
                        sku_no, warehouse_id, warehouse_name, stock_num, available_num,
                        purchase_in_transit_num, synced_at
                    ) VALUES (
                        'TEST-SKU', '1', '主仓库（新）', 330, 330, 0,
                        '2026-08-27T00:00:00'
                    )
                    """
                )
                for index in range(30):
                    movement_date = end - timedelta(days=29 - index)
                    quantity = 80 / 23 if index < 23 else 10
                    connection.execute(
                        """
                        INSERT INTO movements (
                            movement_key, movement_date, event_time, sku_no, warehouse_id,
                            warehouse_name, movement_type, movement_name, out_num, quantity
                        ) VALUES (?, ?, ?, 'TEST-SKU', '1', '主仓库（新）', -1, '销售出库', ?, ?)
                        """,
                        (
                            f"movement-{index}",
                            movement_date.isoformat(),
                            f"{movement_date.isoformat()}T12:00:00",
                            quantity,
                            -quantity,
                        ),
                    )

            result = database.purchase_plan(
                "2026-08-01", "2026-08-27", limit=1000
            )
            row = next(
                item for item in result["items"] if item["sku_no"] == "TEST-SKU"
            )

            # 7-day average = 10; 30-day average = 5; Excel daily = 10*40% + 5*60% = 7.
            self.assertAlmostEqual(row["daily_sales"], 7.0)
            self.assertAlmostEqual(row["trend_coefficient"], 2.0)
            self.assertAlmostEqual(row["trend_purchase_multiplier"], 1.4)
            self.assertEqual(row["purchase_category"], "护腕")
            self.assertAlmostEqual(row["weekly_sales"], 70.0)
            self.assertAlmostEqual(row["target_week_multiplier"], 7.0)
            self.assertAlmostEqual(row["target_stock_qty"], 686.0)
            # Purchase quantity uses the target stock directly. The 330 units
            # already available affect timing only and are not deducted.
            self.assertAlmostEqual(row["raw_order_qty"], 686.0)
            self.assertEqual(row["calculated_order_qty"], 700)
            self.assertEqual(row["final_order_qty"], 700)
            self.assertEqual(row["purchase_formula"], "7A×1.4")
            self.assertEqual(row["order_window"], "固定下单日（每月5日、20日）")
            self.assertEqual(row["suggested_order_date"], "2026-09-05")


if __name__ == "__main__":
    unittest.main()
