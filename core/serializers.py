import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from rest_framework import serializers

from .models import Dealer, Order, OrderItem, OrderStatus, Product

PRICE_REGEX = re.compile(r"^\d+(\.\d{1,2})?$")
GST_RATE = Decimal("0.18")
TWO_DECIMALS = Decimal("0.01")


def format_money(val) -> str:
    if val is None:
        return "0.00"
    if not isinstance(val, Decimal):
        val = Decimal(str(val))
    return f"{val:.2f}"


class ProductSerializer(serializers.ModelSerializer):
    price = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "sku",
            "name",
            "category",
            "brand",
            "vehicle_fitment",
            "price",
            "stock",
            "description",
        ]

    def get_price(self, obj) -> str:
        return format_money(obj.price)


class ProductCreateSerializer(serializers.ModelSerializer):
    price = serializers.CharField()

    class Meta:
        model = Product
        fields = [
            "sku",
            "name",
            "category",
            "brand",
            "vehicle_fitment",
            "price",
            "description",
        ]

    def validate_price(self, value):
        str_val = str(value).strip()
        if not PRICE_REGEX.match(str_val):
            raise serializers.ValidationError("Price must be a positive number with at most 2 decimal places.")
        try:
            dec = Decimal(str_val)
        except InvalidOperation:
            raise serializers.ValidationError("Invalid monetary value.")
        if dec <= 0:
            raise serializers.ValidationError("Price must be strictly positive.")
        return dec


class ProductUpdateSerializer(serializers.ModelSerializer):
    price = serializers.CharField(required=False)

    class Meta:
        model = Product
        fields = [
            "name",
            "category",
            "brand",
            "vehicle_fitment",
            "price",
            "description",
        ]

    def validate_price(self, value):
        str_val = str(value).strip()
        if not PRICE_REGEX.match(str_val):
            raise serializers.ValidationError("Price must be a positive number with at most 2 decimal places.")
        try:
            dec = Decimal(str_val)
        except InvalidOperation:
            raise serializers.ValidationError("Invalid monetary value.")
        if dec <= 0:
            raise serializers.ValidationError("Price must be strictly positive.")
        return dec


class InventoryUpdateSerializer(serializers.Serializer):
    quantity = serializers.IntegerField()
    reason = serializers.CharField(required=False, allow_blank=True)

    def validate_quantity(self, value):
        # Disallow booleans since in Python bool is subclass of int
        if isinstance(self.initial_data.get("quantity"), bool):
            raise serializers.ValidationError("Quantity cannot be a boolean.")
        if value < 0:
            raise serializers.ValidationError("Quantity must be an integer >= 0.")
        return value


class DealerSerializer(serializers.ModelSerializer):
    credit_limit = serializers.SerializerMethodField()

    class Meta:
        model = Dealer
        fields = [
            "id",
            "dealer_code",
            "name",
            "city",
            "phone",
            "email",
            "gstin",
            "credit_limit",
        ]

    def get_credit_limit(self, obj) -> str:
        return format_money(obj.credit_limit)


class DealerCreateSerializer(serializers.ModelSerializer):
    credit_limit = serializers.CharField(required=False, default="0.00")

    class Meta:
        model = Dealer
        fields = [
            "dealer_code",
            "name",
            "city",
            "phone",
            "email",
            "gstin",
            "credit_limit",
        ]

    def validate_credit_limit(self, value):
        if value is None or str(value).strip() == "":
            return Decimal("0.00")
        str_val = str(value).strip()
        if not PRICE_REGEX.match(str_val):
            raise serializers.ValidationError("Credit limit must be a number with at most 2 decimal places.")
        try:
            dec = Decimal(str_val)
        except InvalidOperation:
            raise serializers.ValidationError("Invalid credit limit.")
        if dec < 0:
            raise serializers.ValidationError("Credit limit cannot be negative.")
        return dec


class OrderItemSerializer(serializers.ModelSerializer):
    unit_price = serializers.SerializerMethodField()
    line_subtotal = serializers.SerializerMethodField()
    line_tax = serializers.SerializerMethodField()
    line_total = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = [
            "sku",
            "name",
            "quantity",
            "unit_price",
            "line_subtotal",
            "line_tax",
            "line_total",
        ]

    def _get_live_price(self, obj) -> Decimal:
        if hasattr(obj, "order") and obj.order.status == OrderStatus.DRAFT and hasattr(obj, "product"):
            return obj.product.price
        return obj.unit_price

    def get_unit_price(self, obj) -> str:
        return format_money(self._get_live_price(obj))

    def get_line_subtotal(self, obj) -> str:
        if hasattr(obj, "order") and obj.order.status == OrderStatus.DRAFT and hasattr(obj, "product"):
            sub = (self._get_live_price(obj) * Decimal(obj.quantity)).quantize(TWO_DECIMALS, rounding=ROUND_HALF_UP)
            return format_money(sub)
        return format_money(obj.line_subtotal)

    def get_line_tax(self, obj) -> str:
        if hasattr(obj, "order") and obj.order.status == OrderStatus.DRAFT and hasattr(obj, "product"):
            sub = (self._get_live_price(obj) * Decimal(obj.quantity)).quantize(TWO_DECIMALS, rounding=ROUND_HALF_UP)
            tax = (sub * GST_RATE).quantize(TWO_DECIMALS, rounding=ROUND_HALF_UP)
            return format_money(tax)
        return format_money(obj.line_tax)

    def get_line_total(self, obj) -> str:
        if hasattr(obj, "order") and obj.order.status == OrderStatus.DRAFT and hasattr(obj, "product"):
            sub = (self._get_live_price(obj) * Decimal(obj.quantity)).quantize(TWO_DECIMALS, rounding=ROUND_HALF_UP)
            tax = (sub * GST_RATE).quantize(TWO_DECIMALS, rounding=ROUND_HALF_UP)
            return format_money(sub + tax)
        return format_money(obj.line_total)


class OrderSerializer(serializers.ModelSerializer):
    dealer_id = serializers.IntegerField(source="dealer.id")
    dealer_code = serializers.CharField(source="dealer.dealer_code", read_only=True)
    dealer_name = serializers.CharField(source="dealer.name", read_only=True)
    items = OrderItemSerializer(many=True, read_only=True)
    subtotal = serializers.SerializerMethodField()
    tax_total = serializers.SerializerMethodField()
    grand_total = serializers.SerializerMethodField()
    created_at = serializers.SerializerMethodField()
    updated_at = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "order_number",
            "dealer_id",
            "dealer_code",
            "dealer_name",
            "status",
            "items",
            "subtotal",
            "tax_total",
            "grand_total",
            "created_at",
            "updated_at",
        ]

    def get_subtotal(self, obj) -> str:
        if obj.status == OrderStatus.DRAFT:
            items = obj.items.select_related("product").all()
            sub = sum((it.product.price * Decimal(it.quantity)).quantize(TWO_DECIMALS, rounding=ROUND_HALF_UP) for it in items)
            return format_money(sub)
        return format_money(obj.subtotal)

    def get_tax_total(self, obj) -> str:
        if obj.status == OrderStatus.DRAFT:
            items = obj.items.select_related("product").all()
            tax = sum((((it.product.price * Decimal(it.quantity)).quantize(TWO_DECIMALS, rounding=ROUND_HALF_UP)) * GST_RATE).quantize(TWO_DECIMALS, rounding=ROUND_HALF_UP) for it in items)
            return format_money(tax)
        return format_money(obj.tax_total)

    def get_grand_total(self, obj) -> str:
        if obj.status == OrderStatus.DRAFT:
            items = obj.items.select_related("product").all()
            sub = sum((it.product.price * Decimal(it.quantity)).quantize(TWO_DECIMALS, rounding=ROUND_HALF_UP) for it in items)
            tax = sum((((it.product.price * Decimal(it.quantity)).quantize(TWO_DECIMALS, rounding=ROUND_HALF_UP)) * GST_RATE).quantize(TWO_DECIMALS, rounding=ROUND_HALF_UP) for it in items)
            return format_money(sub + tax)
        return format_money(obj.grand_total)

    def get_created_at(self, obj) -> str:
        return obj.created_at.isoformat()

    def get_updated_at(self, obj) -> str:
        return obj.updated_at.isoformat()
