import hashlib
import json
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo
from django.db import IntegrityError, transaction
from django.utils import timezone

from core.exceptions import (
    IdempotencyConflictException,
    InsufficientStockException,
    InvalidTransitionException,
    NotFoundException,
    OrderLockedException,
    ValidationErrorException,
)
from core.models import (
    Dealer,
    IdempotencyRecord,
    Order,
    OrderDailySequence,
    OrderItem,
    OrderStatus,
    Product,
)

KOLKATA_TZ = ZoneInfo("Asia/Kolkata")
GST_RATE = Decimal("0.18")
TWO_DECIMALS = Decimal("0.01")


def canonical_request_hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def generate_order_number() -> str:
    """Generate ORD-YYYYMMDD-NNNN using Asia/Kolkata date and atomic daily sequence."""
    now_kolkata = timezone.now().astimezone(KOLKATA_TZ)
    today = now_kolkata.date()
    for _ in range(5):
        try:
            with transaction.atomic():
                seq, _ = OrderDailySequence.objects.select_for_update().get_or_create(date=today)
                seq.last_number += 1
                seq.save(update_fields=["last_number"])
                return f"ORD-{today.strftime('%Y%m%d')}-{seq.last_number:04d}"
        except IntegrityError:
            continue
    raise RuntimeError("Failed to allocate atomic daily order sequence number.")


def validate_and_parse_order_items(items_data):
    """Validate items list ensuring positive quantities, existing products, and no duplicates."""
    if not isinstance(items_data, list) or len(items_data) == 0:
        raise ValidationErrorException("Order items list must contain at least one item.")

    seen_skus = set()
    cleaned_items = []
    for idx, item in enumerate(items_data):
        if not isinstance(item, dict):
            raise ValidationErrorException(f"Item at index {idx} must be a dictionary.")
        sku = item.get("sku")
        if not sku or not isinstance(sku, str) or not sku.strip():
            raise ValidationErrorException(f"Item at index {idx} must have a non-empty SKU.")
        sku = sku.strip()
        if sku in seen_skus:
            raise ValidationErrorException(f"Duplicate SKU '{sku}' in order items.")
        seen_skus.add(sku)

        quantity = item.get("quantity")
        if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 1:
            raise ValidationErrorException(f"Quantity for SKU '{sku}' must be an integer >= 1.")

        cleaned_items.append({"sku": sku, "quantity": quantity})

    # Validate that every SKU exists in database
    products = {p.sku: p for p in Product.objects.filter(sku__in=seen_skus)}
    for item in cleaned_items:
        sku = item["sku"]
        if sku not in products:
            raise ValidationErrorException(f"Product with SKU '{sku}' does not exist.")
        item["product"] = products[sku]

    return cleaned_items


def compute_financials(parsed_items):
    """Compute line totals and order totals with ROUND_HALF_UP 18% GST."""
    subtotal = Decimal("0.00")
    tax_total = Decimal("0.00")
    item_rows = []

    for item in parsed_items:
        product = item["product"]
        quantity = item["quantity"]
        unit_price = product.price
        line_subtotal = (unit_price * Decimal(quantity)).quantize(TWO_DECIMALS, rounding=ROUND_HALF_UP)
        line_tax = (line_subtotal * GST_RATE).quantize(TWO_DECIMALS, rounding=ROUND_HALF_UP)
        line_total = line_subtotal + line_tax

        subtotal += line_subtotal
        tax_total += line_tax
        item_rows.append(
            {
                "product": product,
                "sku": product.sku,
                "name": product.name,
                "quantity": quantity,
                "unit_price": unit_price,
                "line_subtotal": line_subtotal,
                "line_tax": line_tax,
                "line_total": line_total,
            }
        )

    grand_total = subtotal + tax_total
    return subtotal, tax_total, grand_total, item_rows


@transaction.atomic
def create_draft_order(dealer_id: int, items_data: list, idempotency_key: str = None):
    """Create a new DRAFT order with transactional idempotency handling."""
    req_hash = None
    if idempotency_key:
        payload = {"dealer_id": dealer_id, "items": items_data}
        req_hash = canonical_request_hash(payload)

        # On PostgreSQL, lock on idempotency key to prevent simultaneous creation races
        from django.db import connection
        if connection.vendor == "postgresql":
            raw_hash = int(hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()[:15], 16)
            lock_id = raw_hash - (1 << 59)
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(%s)", [lock_id])

        record = IdempotencyRecord.objects.select_for_update().filter(key=idempotency_key).first()
        if record:
            if record.request_hash == req_hash:
                return record.response_data, record.response_status
            else:
                raise IdempotencyConflictException("Idempotency-Key reused with different request body.")

    # Validate dealer
    try:
        dealer = Dealer.objects.get(id=dealer_id)
    except Dealer.DoesNotExist:
        raise ValidationErrorException(f"Dealer with id {dealer_id} does not exist.")

    # Validate items
    parsed_items = validate_and_parse_order_items(items_data)

    # Compute financials
    subtotal, tax_total, grand_total, item_rows = compute_financials(parsed_items)

    # Generate atomic order number
    order_number = generate_order_number()

    order = Order.objects.create(
        order_number=order_number,
        dealer=dealer,
        status=OrderStatus.DRAFT,
        subtotal=subtotal,
        tax_total=tax_total,
        grand_total=grand_total,
    )

    order_items = [
        OrderItem(
            order=order,
            product=r["product"],
            sku=r["sku"],
            name=r["name"],
            quantity=r["quantity"],
            unit_price=r["unit_price"],
            line_subtotal=r["line_subtotal"],
            line_tax=r["line_tax"],
            line_total=r["line_total"],
        )
        for r in item_rows
    ]
    OrderItem.objects.bulk_create(order_items)

    from core.serializers import OrderSerializer
    response_data = OrderSerializer(order).data

    if idempotency_key:
        try:
            with transaction.atomic():
                IdempotencyRecord.objects.create(
                    key=idempotency_key,
                    request_hash=req_hash,
                    order=order,
                    response_status=201,
                    response_data=response_data,
                )
        except IntegrityError:
            rec = IdempotencyRecord.objects.filter(key=idempotency_key).first()
            if rec and rec.request_hash == req_hash:
                return rec.response_data, rec.response_status
            raise IdempotencyConflictException("Idempotency-Key reused with different request body.")

    return response_data, 201


@transaction.atomic
def update_draft_order(order_number: str, items_data: list):
    """Update items of a DRAFT order. Rejects if not in DRAFT status."""
    order = Order.objects.select_for_update().filter(order_number=order_number).first()
    if not order:
        raise NotFoundException(f"Order '{order_number}' not found.")

    if order.status != OrderStatus.DRAFT:
        raise OrderLockedException("Only DRAFT orders can be updated.")

    parsed_items = validate_and_parse_order_items(items_data)
    subtotal, tax_total, grand_total, item_rows = compute_financials(parsed_items)

    order.items.all().delete()

    order.subtotal = subtotal
    order.tax_total = tax_total
    order.grand_total = grand_total
    order.save(update_fields=["subtotal", "tax_total", "grand_total", "updated_at"])

    order_items = [
        OrderItem(
            order=order,
            product=r["product"],
            sku=r["sku"],
            name=r["name"],
            quantity=r["quantity"],
            unit_price=r["unit_price"],
            line_subtotal=r["line_subtotal"],
            line_tax=r["line_tax"],
            line_total=r["line_total"],
        )
        for r in item_rows
    ]
    OrderItem.objects.bulk_create(order_items)

    from core.serializers import OrderSerializer
    return OrderSerializer(order).data


@transaction.atomic
def confirm_order(order_number: str):
    """Confirm a DRAFT order atomically with row locking to prevent overselling."""
    order = Order.objects.select_for_update().filter(order_number=order_number).first()
    if not order:
        raise NotFoundException(f"Order '{order_number}' not found.")

    if order.status != OrderStatus.DRAFT:
        raise InvalidTransitionException(f"Cannot confirm order in status '{order.status}'.")

    items = list(order.items.select_related("product").all())
    product_ids = [item.product_id for item in items]

    # Lock product rows in deterministic SKU order to prevent deadlocks
    products_locked = {
        p.id: p
        for p in Product.objects.filter(id__in=product_ids).order_by("sku").select_for_update()
    }

    # Validate stock across all lines
    shortages = []
    messages = []
    for item in items:
        p = products_locked.get(item.product_id)
        if not p or p.stock < item.quantity:
            avail = p.stock if p else 0
            shortages.append(
                {
                    "sku": item.sku,
                    "requested": item.quantity,
                    "available": avail,
                }
            )
            name = p.name if p else item.name
            messages.append(
                f"Insufficient stock for {name}. Available: {avail}, Requested: {item.quantity}"
            )

    if shortages:
        raise InsufficientStockException(
            message="; ".join(messages),
            details=shortages,
        )

    # Deduct stock atomically and lock unit price snapshot
    subtotal = Decimal("0.00")
    tax_total = Decimal("0.00")
    for item in items:
        p = products_locked[item.product_id]
        p.stock -= item.quantity
        p.save(update_fields=["stock", "updated_at"])

        # Lock current unit price snapshot forever
        item.unit_price = p.price
        item.line_subtotal = (p.price * Decimal(item.quantity)).quantize(TWO_DECIMALS, rounding=ROUND_HALF_UP)
        item.line_tax = (item.line_subtotal * GST_RATE).quantize(TWO_DECIMALS, rounding=ROUND_HALF_UP)
        item.line_total = item.line_subtotal + item.line_tax
        item.save(update_fields=["unit_price", "line_subtotal", "line_tax", "line_total"])

        subtotal += item.line_subtotal
        tax_total += item.line_tax

    order.subtotal = subtotal
    order.tax_total = tax_total
    order.grand_total = subtotal + tax_total
    order.status = OrderStatus.CONFIRMED
    order.save(update_fields=["status", "subtotal", "tax_total", "grand_total", "updated_at"])

    from core.serializers import OrderSerializer
    return OrderSerializer(order).data


@transaction.atomic
def dispatch_order(order_number: str):
    """Transition order CONFIRMED -> DISPATCHED."""
    order = Order.objects.select_for_update().filter(order_number=order_number).first()
    if not order:
        raise NotFoundException(f"Order '{order_number}' not found.")

    if order.status != OrderStatus.CONFIRMED:
        raise InvalidTransitionException(f"Cannot dispatch order in status '{order.status}'.")

    order.status = OrderStatus.DISPATCHED
    order.save(update_fields=["status", "updated_at"])

    from core.serializers import OrderSerializer
    return OrderSerializer(order).data


@transaction.atomic
def deliver_order(order_number: str):
    """Transition order DISPATCHED -> DELIVERED."""
    order = Order.objects.select_for_update().filter(order_number=order_number).first()
    if not order:
        raise NotFoundException(f"Order '{order_number}' not found.")

    if order.status != OrderStatus.DISPATCHED:
        raise InvalidTransitionException(f"Cannot deliver order in status '{order.status}'.")

    order.status = OrderStatus.DELIVERED
    order.save(update_fields=["status", "updated_at"])

    from core.serializers import OrderSerializer
    return OrderSerializer(order).data


@transaction.atomic
def cancel_order(order_number: str):
    """Cancel DRAFT or CONFIRMED order. Restores stock exactly once for CONFIRMED orders."""
    order = Order.objects.select_for_update().filter(order_number=order_number).first()
    if not order:
        raise NotFoundException(f"Order '{order_number}' not found.")

    if order.status not in (OrderStatus.DRAFT, OrderStatus.CONFIRMED):
        raise InvalidTransitionException(f"Cannot cancel order in status '{order.status}'.")

    if order.status == OrderStatus.CONFIRMED:
        items = list(order.items.select_related("product").all())
        product_ids = [item.product_id for item in items]
        products_locked = {
            p.id: p
            for p in Product.objects.filter(id__in=product_ids).order_by("sku").select_for_update()
        }
        for item in items:
            p = products_locked.get(item.product_id)
            if p:
                p.stock += item.quantity
                p.save(update_fields=["stock", "updated_at"])

    order.status = OrderStatus.CANCELLED
    order.save(update_fields=["status", "updated_at"])

    from core.serializers import OrderSerializer
    return OrderSerializer(order).data
