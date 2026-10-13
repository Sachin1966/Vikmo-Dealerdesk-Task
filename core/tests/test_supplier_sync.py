from decimal import Decimal
from unittest.mock import MagicMock, patch
from django.test import TestCase
from rest_framework.test import APIClient
from core.models import Product
from core.services.supplier_sync import sync_supplier_catalogue, validate_supplier_item


class SupplierSyncTests(TestCase):
    def test_validate_supplier_item(self):
        """Validates pricing, SKU presence, and decimal constraints."""
        ok_item = {"sku": "SYNC-01", "price": "199.99", "name": "Item"}
        is_val, reason, dec = validate_supplier_item(ok_item)
        self.assertTrue(is_val)
        self.assertEqual(dec, Decimal("199.99"))

        # Missing SKU
        bad_sku = {"sku": "", "price": "199.99"}
        is_val, reason, _ = validate_supplier_item(bad_sku)
        self.assertFalse(is_val)
        self.assertEqual(reason, "missing or empty sku")

        # Negative price
        bad_price = {"sku": "SYNC-02", "price": "-50.00"}
        is_val, reason, _ = validate_supplier_item(bad_price)
        self.assertFalse(is_val)
        self.assertEqual(reason, "invalid price")

        # More than 2 decimal places
        bad_dec = {"sku": "SYNC-03", "price": "50.123"}
        is_val, reason, _ = validate_supplier_item(bad_dec)
        self.assertFalse(is_val)
        self.assertEqual(reason, "invalid price")

    @patch("core.services.supplier_sync.requests.get")
    def test_sync_deduplication_and_stock_preservation(self, mock_get):
        """Deduplicates multiple versions of same SKU by latest updated_at; does not touch stock."""
        Product.objects.create(
            sku="SYNC-EXISTS",
            name="Old Name",
            category="Brakes",
            brand="Old Brand",
            vehicle_fitment="Pulsar",
            price=Decimal("100.00"),
            stock=42,  # Existing stock
        )

        # Mock 1 page with 2 entries for SYNC-EXISTS and 1 new entry
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "items": [
                {
                    "supplier_sku": "SUP-1",
                    "sku": "SYNC-EXISTS",
                    "name": "Outdated Name",
                    "category": "Brakes",
                    "brand": "New Brand",
                    "vehicle_fitment": "Pulsar 150",
                    "price": "120.00",
                    "supplier_stock": 500,
                    "updated_at": "2026-10-01T10:00:00Z",
                },
                {
                    "supplier_sku": "SUP-2",
                    "sku": "SYNC-EXISTS",
                    "name": "Latest Name",
                    "category": "Brakes",
                    "brand": "New Brand",
                    "vehicle_fitment": "Pulsar 150",
                    "price": "125.00",
                    "supplier_stock": 600,
                    "updated_at": "2026-10-05T12:00:00Z",
                },
                {
                    "supplier_sku": "SUP-3",
                    "sku": "SYNC-BRANDNEW",
                    "name": "Brand New Part",
                    "category": "Engine",
                    "brand": "NGK",
                    "vehicle_fitment": "Universal",
                    "price": "300.00",
                    "supplier_stock": 100,
                    "updated_at": "2026-10-05T12:00:00Z",
                },
            ],
            "next_cursor": None,
        }
        mock_get.return_value = mock_resp

        result = sync_supplier_catalogue()
        self.assertEqual(result["created"], 1)
        self.assertEqual(result["updated"], 1)
        self.assertEqual(result["unchanged"], 0)

        # Verify existing product updated with latest data, but stock remained 42
        p_existing = Product.objects.get(sku="SYNC-EXISTS")
        self.assertEqual(p_existing.name, "Latest Name")
        self.assertEqual(p_existing.price, Decimal("125.00"))
        self.assertEqual(p_existing.stock, 42)

        # Verify new product created with stock 0
        p_new = Product.objects.get(sku="SYNC-BRANDNEW")
        self.assertEqual(p_new.stock, 0)
