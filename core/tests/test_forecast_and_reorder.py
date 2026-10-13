import csv
import math
import os
from decimal import Decimal
from django.conf import settings
from django.test import TestCase
from rest_framework.test import APIClient
from core.models import Product


class ForecastAndReorderTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_forecast_file_format_and_coverage(self):
        """forecast.csv must contain exactly 160 rows for 40 SKUs across the 4 forecast weeks."""
        csv_path = settings.BASE_DIR / "ml" / "forecast.csv"
        self.assertTrue(os.path.exists(csv_path), "ml/forecast.csv does not exist.")

        with open(csv_path, encoding="utf-8") as f:
            reader = list(csv.DictReader(f))

        self.assertEqual(len(reader), 160)
        expected_cols = ["sku", "week_start", "forecast_units"]
        self.assertEqual(list(reader[0].keys())[:3], expected_cols)

        expected_weeks = {"2026-09-28", "2026-10-05", "2026-10-12", "2026-10-19"}
        found_weeks = {r["week_start"] for r in reader}
        self.assertEqual(found_weeks, expected_weeks)

        for r in reader:
            val = float(r["forecast_units"])
            self.assertGreaterEqual(val, 0.0)

    def test_reorder_suggestions_endpoint(self):
        """GET /api/reorder-suggestions/ must return exactly 40 items with exact formula fields."""
        res = self.client.get("/api/reorder-suggestions/")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("results", data)
        results = data["results"]
        self.assertEqual(len(results), 40)

        required_keys = [
            "sku",
            "current_stock",
            "lead_time_weeks",
            "lead_time_demand",
            "safety_stock",
            "reorder_point",
            "reorder_qty",
        ]
        for item in results:
            for k in required_keys:
                self.assertIn(k, item)
            # Reorder quantity must equal max(0, ceil(reorder_point - current_stock))
            expected_qty = max(0, math.ceil(item["reorder_point"] - item["current_stock"]))
            self.assertEqual(item["reorder_qty"], expected_qty)
