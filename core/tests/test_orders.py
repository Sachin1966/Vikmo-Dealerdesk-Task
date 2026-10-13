from decimal import Decimal
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIClient
from core.models import Dealer, Order, OrderItem, OrderStatus, Product


class OrderBusinessRulesTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.dealer = Dealer.objects.create(
            dealer_code="DLR-TEST01",
            name="Test Auto Spares",
            city="Pune",
            credit_limit=Decimal("50000.00"),
        )
        self.product1 = Product.objects.create(
            sku="TST-1001",
            name="Disc Brake Pad",
            category="Brakes",
            brand="Brembo",
            vehicle_fitment="Yamaha R15",
            price=Decimal("100.00"),
            stock=10,
        )
        self.product2 = Product.objects.create(
            sku="TST-1002",
            name="Engine Oil 1L",
            category="Lubricants",
            brand="Motul",
            vehicle_fitment="Universal",
            price=Decimal("50.55"),
            stock=5,
        )

    def test_create_draft_order_exact_gst(self):
        """Test exact GST calculation per line with ROUND_HALF_UP."""
        # 3 units of product 2: 3 * 50.55 = 151.65.
        # Tax = 151.65 * 0.18 = 27.297 -> 27.30 (ROUND_HALF_UP).
        # Line total = 151.65 + 27.30 = 178.95.
        res = self.client.post(
            "/api/orders/",
            {"dealer_id": self.dealer.id, "items": [{"sku": "TST-1002", "quantity": 3}]},
            format="json",
        )
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertEqual(data["status"], "DRAFT")
        self.assertEqual(data["subtotal"], "151.65")
        self.assertEqual(data["tax_total"], "27.30")
        self.assertEqual(data["grand_total"], "178.95")

    def test_order_number_format(self):
        """Order number must follow ORD-YYYYMMDD-NNNN."""
        res = self.client.post(
            "/api/orders/",
            {"dealer_id": self.dealer.id, "items": [{"sku": "TST-1001", "quantity": 1}]},
            format="json",
        )
        self.assertEqual(res.status_code, 201)
        order_no = res.json()["order_number"]
        self.assertRegex(order_no, r"^ORD-\d{8}-\d{4}$")

    def test_idempotency_key_duplicate_and_conflict(self):
        """Identical payload with same Idempotency-Key returns same order; modified payload returns 409."""
        headers = {"HTTP_IDEMPOTENCY_KEY": "idem-key-test-123"}
        payload1 = {"dealer_id": self.dealer.id, "items": [{"sku": "TST-1001", "quantity": 1}]}

        res1 = self.client.post("/api/orders/", payload1, format="json", **headers)
        self.assertEqual(res1.status_code, 201)
        order_num1 = res1.json()["order_number"]

        # Duplicate request with same key & body
        res2 = self.client.post("/api/orders/", payload1, format="json", **headers)
        self.assertEqual(res2.status_code, 201)
        self.assertEqual(res2.json()["order_number"], order_num1)

        # Reusing same key with different body must return 409 IDEMPOTENCY_CONFLICT
        payload2 = {"dealer_id": self.dealer.id, "items": [{"sku": "TST-1001", "quantity": 2}]}
        res3 = self.client.post("/api/orders/", payload2, format="json", **headers)
        self.assertEqual(res3.status_code, 409)
        self.assertEqual(res3.json()["error"]["code"], "IDEMPOTENCY_CONFLICT")

    def test_price_lock_on_confirmation(self):
        """Price follows catalogue while DRAFT, but is permanently frozen on confirm."""
        res = self.client.post(
            "/api/orders/",
            {"dealer_id": self.dealer.id, "items": [{"sku": "TST-1001", "quantity": 2}]},
            format="json",
        )
        order_no = res.json()["order_number"]

        # Update product catalogue price while order is DRAFT
        self.product1.price = Decimal("200.00")
        self.product1.save()

        # DRAFT order reflects new price: 2 * 200 = 400.00 subtotal
        draft_check = self.client.get(f"/api/orders/{order_no}/")
        self.assertEqual(draft_check.json()["subtotal"], "400.00")

        # Confirm order locks the 200.00 price
        conf_res = self.client.post(f"/api/orders/{order_no}/confirm/")
        self.assertEqual(conf_res.status_code, 200)
        self.assertEqual(conf_res.json()["status"], "CONFIRMED")
        self.assertEqual(conf_res.json()["subtotal"], "400.00")

        # Later change in catalogue price has no effect on confirmed order
        self.product1.price = Decimal("350.00")
        self.product1.save()

        locked_check = self.client.get(f"/api/orders/{order_no}/")
        self.assertEqual(locked_check.json()["subtotal"], "400.00")

    def test_status_transitions_and_restoration(self):
        """CONFIRMED order deducts stock; CANCELLED restores stock once."""
        res = self.client.post(
            "/api/orders/",
            {"dealer_id": self.dealer.id, "items": [{"sku": "TST-1001", "quantity": 4}]},
            format="json",
        )
        order_no = res.json()["order_number"]

        # Initial stock is 10; confirm reduces to 6
        self.client.post(f"/api/orders/{order_no}/confirm/")
        self.product1.refresh_from_db()
        self.assertEqual(self.product1.stock, 6)

        # Disallow editing confirmed order
        edit_res = self.client.put(
            f"/api/orders/{order_no}/",
            {"items": [{"sku": "TST-1001", "quantity": 1}]},
            format="json",
        )
        self.assertEqual(edit_res.status_code, 409)
        self.assertEqual(edit_res.json()["error"]["code"], "ORDER_LOCKED")

        # Cancel restores stock to 10
        cancel_res = self.client.post(f"/api/orders/{order_no}/cancel/")
        self.assertEqual(cancel_res.status_code, 200)
        self.product1.refresh_from_db()
        self.assertEqual(self.product1.stock, 10)

        # Cancel cannot be called again
        cancel_again = self.client.post(f"/api/orders/{order_no}/cancel/")
        self.assertEqual(cancel_again.status_code, 409)
        self.assertEqual(cancel_again.json()["error"]["code"], "INVALID_TRANSITION")


class OrderConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.client = APIClient()
        self.dealer = Dealer.objects.create(
            dealer_code="DLR-CONC01",
            name="Concurrent Spares",
        )
        self.product = Product.objects.create(
            sku="CONC-9999",
            name="Limited Stock Gear",
            category="Gears",
            brand="Endurance",
            vehicle_fitment="Universal",
            price=Decimal("500.00"),
            stock=5,  # Only 5 in stock
        )

    def test_overselling_prevented(self):
        """When two orders each request 4 units with only 5 available, one succeeds and the other gets 409."""
        # Create order 1 for 4 units
        o1 = self.client.post(
            "/api/orders/",
            {"dealer_id": self.dealer.id, "items": [{"sku": "CONC-9999", "quantity": 4}]},
            format="json",
        ).json()["order_number"]

        # Create order 2 for 4 units
        o2 = self.client.post(
            "/api/orders/",
            {"dealer_id": self.dealer.id, "items": [{"sku": "CONC-9999", "quantity": 4}]},
            format="json",
        ).json()["order_number"]

        res1 = self.client.post(f"/api/orders/{o1}/confirm/")
        self.assertEqual(res1.status_code, 200)

        res2 = self.client.post(f"/api/orders/{o2}/confirm/")
        self.assertEqual(res2.status_code, 409)
        self.assertEqual(res2.json()["error"]["code"], "INSUFFICIENT_STOCK")

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 1)
