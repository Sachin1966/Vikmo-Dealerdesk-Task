from decimal import Decimal
from django.test import TestCase
from rest_framework.test import APIClient
from core.models import Product


class ProductAndInventoryTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.product = Product.objects.create(
            sku="INV-1001",
            name="Spark Plug",
            category="Electrical",
            brand="NGK",
            vehicle_fitment="Bajaj Pulsar 150",
            price=Decimal("150.00"),
            stock=20,
        )

    def test_create_product_stock_zero_and_validation(self):
        """New products start with stock 0 regardless of payload; price must be positive with at most 2 decimals."""
        res = self.client.post(
            "/api/products/",
            {
                "sku": "NEW-2002",
                "name": "Clutch Cable",
                "category": "Cables",
                "brand": "Endurance",
                "vehicle_fitment": "KTM Duke 390",
                "price": "349.50",
                "stock": 50,  # Must be ignored / set to 0
            },
            format="json",
        )
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertEqual(data["stock"], 0)
        self.assertEqual(data["price"], "349.50")

        # Duplicate SKU -> 409 DUPLICATE
        dup = self.client.post(
            "/api/products/",
            {
                "sku": "NEW-2002",
                "name": "Another Cable",
                "category": "Cables",
                "brand": "Endurance",
                "vehicle_fitment": "KTM Duke 390",
                "price": "100.00",
            },
            format="json",
        )
        self.assertEqual(dup.status_code, 409)
        self.assertEqual(dup.json()["error"]["code"], "DUPLICATE")

        # Invalid price (3 decimals) -> 400
        bad_price = self.client.post(
            "/api/products/",
            {
                "sku": "BAD-PRICE",
                "name": "Test",
                "category": "Cables",
                "brand": "Endurance",
                "vehicle_fitment": "Universal",
                "price": "100.999",
            },
            format="json",
        )
        self.assertEqual(bad_price.status_code, 400)

    def test_inventory_update(self):
        """PUT /api/inventory/{sku}/ updates stock to exact non-negative integer."""
        res = self.client.put(
            f"/api/inventory/{self.product.sku}/",
            {"quantity": 75, "reason": "stock audit correction"},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), {"sku": self.product.sku, "quantity": 75})
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 75)

        # Reject negative quantity -> 400
        neg = self.client.put(
            f"/api/inventory/{self.product.sku}/",
            {"quantity": -10},
            format="json",
        )
        self.assertEqual(neg.status_code, 400)
