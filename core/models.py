from decimal import Decimal
from django.db import models
from django.db.models import CheckConstraint, Q


class Product(models.Model):
    sku = models.CharField(max_length=64, unique=True, db_index=True)
    name = models.CharField(max_length=255)
    category = models.CharField(max_length=128, db_index=True)
    brand = models.CharField(max_length=128, db_index=True)
    vehicle_fitment = models.CharField(max_length=255, db_index=True)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    stock = models.IntegerField(default=0)
    description = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sku"]
        constraints = [
            CheckConstraint(check=Q(stock__gte=0), name="check_product_stock_non_negative"),
            CheckConstraint(check=Q(price__gt=0), name="check_product_price_positive"),
        ]

    def __str__(self):
        return f"{self.sku} - {self.name}"


class Dealer(models.Model):
    dealer_code = models.CharField(max_length=64, unique=True, db_index=True)
    name = models.CharField(max_length=255)
    city = models.CharField(max_length=128, blank=True, default="")
    phone = models.CharField(max_length=32, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    gstin = models.CharField(max_length=32, blank=True, default="")
    credit_limit = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.dealer_code} - {self.name}"


class OrderStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    CONFIRMED = "CONFIRMED", "Confirmed"
    DISPATCHED = "DISPATCHED", "Dispatched"
    DELIVERED = "DELIVERED", "Delivered"
    CANCELLED = "CANCELLED", "Cancelled"


class Order(models.Model):
    order_number = models.CharField(max_length=32, unique=True, db_index=True)
    dealer = models.ForeignKey(Dealer, on_delete=models.PROTECT, related_name="orders")
    status = models.CharField(
        max_length=20,
        choices=OrderStatus.choices,
        default=OrderStatus.DRAFT,
        db_index=True,
    )
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    tax_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    grand_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.order_number} ({self.status})"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="order_items")
    sku = models.CharField(max_length=64)
    name = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    line_subtotal = models.DecimalField(max_digits=14, decimal_places=2)
    line_tax = models.DecimalField(max_digits=14, decimal_places=2)
    line_total = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(fields=["order", "product"], name="unique_order_product"),
            CheckConstraint(check=Q(quantity__gte=1), name="check_order_item_quantity_gte_1"),
        ]

    def __str__(self):
        return f"{self.sku} x {self.quantity}"


class OrderDailySequence(models.Model):
    """Tracks atomic sequential order number generation per calendar day."""
    date = models.DateField(unique=True, db_index=True)
    last_number = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.date}: {self.last_number}"


class IdempotencyRecord(models.Model):
    """Persists idempotency keys, request hashes, and cached responses."""
    key = models.CharField(max_length=255, unique=True, db_index=True)
    request_hash = models.CharField(max_length=64)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, null=True, blank=True)
    response_status = models.IntegerField()
    response_data = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"IdempotencyRecord({self.key})"
