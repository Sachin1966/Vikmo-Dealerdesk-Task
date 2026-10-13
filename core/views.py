import csv
import json
import math
import os
import re
from decimal import Decimal
from django.conf import settings
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from core.exceptions import (
    DuplicateException,
    NotFoundException,
    ValidationErrorException,
)
from core.models import Dealer, Order, Product
from core.pagination import ContractPagination
from core.serializers import (
    DealerCreateSerializer,
    DealerSerializer,
    InventoryUpdateSerializer,
    OrderSerializer,
    ProductCreateSerializer,
    ProductSerializer,
    ProductUpdateSerializer,
)
from core.services.orders import (
    cancel_order,
    confirm_order,
    create_draft_order,
    deliver_order,
    dispatch_order,
    update_draft_order,
)
from core.services.supplier_sync import sync_supplier_catalogue
from core.services.assistant import handle_assistant_turn



# ---- 0. Dealer Portal (Part E) --------------------------------------------------------
def portal_view(request):
    """GET / or /portal/ -> Renders interactive Dealer Portal SPA."""
    return render(request, "portal.html")


# ---- 1. Health ------------------------------------------------------------------------
def health(request):
    """GET /api/health/ -> 200 {"status": "ok"}"""
    return JsonResponse({"status": "ok"})


# ---- 2. Products ----------------------------------------------------------------------
@api_view(["GET", "POST"])
def product_list_create(request):
    """
    GET /api/products/  - paginated list with search, category, vehicle filters.
    POST /api/products/ - create product with initial stock 0.
    """
    if request.method == "GET":
        qs = Product.objects.all().order_by("sku")

        search = request.query_params.get("search")
        if search:
            qs = qs.filter(
                Q(sku__icontains=search)
                | Q(name__icontains=search)
                | Q(brand__icontains=search)
            )

        category = request.query_params.get("category")
        if category:
            qs = qs.filter(category__iexact=category)

        vehicle = request.query_params.get("vehicle")
        if vehicle:
            qs = qs.filter(vehicle_fitment__icontains=vehicle)

        paginator = ContractPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = ProductSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    elif request.method == "POST":
        sku = request.data.get("sku")
        if not sku or not str(sku).strip():
            raise ValidationErrorException("SKU is required.")
        sku = str(sku).strip()

        if Product.objects.filter(sku=sku).exists():
            raise DuplicateException(f"Product with SKU '{sku}' already exists.")

        serializer = ProductCreateSerializer(data=request.data)
        if not serializer.is_valid():
            errors = []
            for field, errs in serializer.errors.items():
                errors.append(f"{field}: {', '.join(str(e) for e in errs)}")
            raise ValidationErrorException("; ".join(errors))

        validated = serializer.validated_data
        product = Product.objects.create(
            sku=sku,
            name=validated.get("name", ""),
            category=validated.get("category", ""),
            brand=validated.get("brand", ""),
            vehicle_fitment=validated.get("vehicle_fitment", ""),
            price=validated.get("price"),
            stock=0,  # Contract: newly created products start with stock 0
            description=validated.get("description", ""),
        )
        return Response(ProductSerializer(product).data, status=status.HTTP_201_CREATED)


@api_view(["GET", "PATCH"])
def product_detail(request, sku):
    """
    GET /api/products/{sku}/   - retrieve product by SKU.
    PATCH /api/products/{sku}/ - partial update (SKU immutable).
    """
    product = Product.objects.filter(sku=sku).first()
    if not product:
        raise NotFoundException(f"Product with SKU '{sku}' not found.")

    if request.method == "GET":
        return Response(ProductSerializer(product).data)

    elif request.method == "PATCH":
        if "sku" in request.data and request.data["sku"] != sku:
            raise ValidationErrorException("Product SKU cannot be changed.")

        serializer = ProductUpdateSerializer(product, data=request.data, partial=True)
        if not serializer.is_valid():
            errors = []
            for field, errs in serializer.errors.items():
                errors.append(f"{field}: {', '.join(str(e) for e in errs)}")
            raise ValidationErrorException("; ".join(errors))

        serializer.save()
        return Response(ProductSerializer(product).data)


# ---- 3. Inventory ---------------------------------------------------------------------
@api_view(["PUT"])
def inventory_update(request, sku):
    """
    PUT /api/inventory/{sku}/ - sets available stock to exact non-negative integer quantity.
    """
    product = Product.objects.filter(sku=sku).first()
    if not product:
        raise NotFoundException(f"Product with SKU '{sku}' not found.")

    serializer = InventoryUpdateSerializer(data=request.data)
    if not serializer.is_valid():
        errors = []
        for field, errs in serializer.errors.items():
            errors.append(f"{field}: {', '.join(str(e) for e in errs)}")
        raise ValidationErrorException("; ".join(errors))

    quantity = serializer.validated_data["quantity"]
    product.stock = quantity
    product.save(update_fields=["stock", "updated_at"])

    return Response({"sku": product.sku, "quantity": product.stock})


# ---- 4. Dealers -----------------------------------------------------------------------
@api_view(["GET", "POST"])
def dealer_list_create(request):
    """
    GET /api/dealers/  - paginated list.
    POST /api/dealers/ - create dealer (dealer_code, name required).
    """
    if request.method == "GET":
        qs = Dealer.objects.all().order_by("id")
        paginator = ContractPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = DealerSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    elif request.method == "POST":
        dealer_code = request.data.get("dealer_code")
        if not dealer_code or not str(dealer_code).strip():
            raise ValidationErrorException("dealer_code is required.")
        dealer_code = str(dealer_code).strip()

        if Dealer.objects.filter(dealer_code=dealer_code).exists():
            raise DuplicateException(f"Dealer with dealer_code '{dealer_code}' already exists.")

        serializer = DealerCreateSerializer(data=request.data)
        if not serializer.is_valid():
            errors = []
            for field, errs in serializer.errors.items():
                errors.append(f"{field}: {', '.join(str(e) for e in errs)}")
            raise ValidationErrorException("; ".join(errors))

        dealer = serializer.save()
        return Response(DealerSerializer(dealer).data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
def dealer_detail(request, pk):
    """GET /api/dealers/{id}/ -> 200 dealer or 404"""
    dealer = Dealer.objects.filter(id=pk).first()
    if not dealer:
        raise NotFoundException(f"Dealer with id {pk} not found.")
    return Response(DealerSerializer(dealer).data)


# ---- 5. Orders ------------------------------------------------------------------------
@api_view(["GET", "POST"])
def order_list_create(request):
    """
    GET /api/orders/  - paginated list with dealer_id and status filters.
    POST /api/orders/ - create DRAFT order, supports Idempotency-Key.
    """
    if request.method == "GET":
        qs = Order.objects.all().prefetch_related("items").order_by("-created_at")

        dealer_id = request.query_params.get("dealer_id")
        if dealer_id:
            try:
                qs = qs.filter(dealer_id=int(dealer_id))
            except ValueError:
                pass

        status_param = request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param.upper())

        paginator = ContractPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = OrderSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    elif request.method == "POST":
        dealer_id = request.data.get("dealer_id")
        items_data = request.data.get("items")
        if dealer_id is None or items_data is None:
            raise ValidationErrorException("Both dealer_id and items are required.")

        idempotency_key = request.headers.get("Idempotency-Key")
        data, status_code = create_draft_order(
            dealer_id=dealer_id,
            items_data=items_data,
            idempotency_key=idempotency_key,
        )
        return Response(data, status=status_code)


@api_view(["GET", "PUT"])
def order_detail_update(request, order_number):
    """
    GET /api/orders/{order_number}/ - order detail.
    PUT /api/orders/{order_number}/ - replace items of DRAFT order.
    """
    if request.method == "GET":
        order = (
            Order.objects.filter(order_number=order_number)
            .prefetch_related("items")
            .first()
        )
        if not order:
            raise NotFoundException(f"Order '{order_number}' not found.")
        return Response(OrderSerializer(order).data)

    elif request.method == "PUT":
        items_data = request.data.get("items")
        if items_data is None:
            raise ValidationErrorException("items list is required.")
        data = update_draft_order(order_number=order_number, items_data=items_data)
        return Response(data)


@api_view(["POST"])
def order_confirm(request, order_number):
    """POST /api/orders/{order_number}/confirm/"""
    data = confirm_order(order_number)
    return Response(data)


@api_view(["POST"])
def order_dispatch(request, order_number):
    """POST /api/orders/{order_number}/dispatch/"""
    data = dispatch_order(order_number)
    return Response(data)


@api_view(["POST"])
def order_deliver(request, order_number):
    """POST /api/orders/{order_number}/deliver/"""
    data = deliver_order(order_number)
    return Response(data)


@api_view(["POST"])
def order_cancel(request, order_number):
    """POST /api/orders/{order_number}/cancel/"""
    data = cancel_order(order_number)
    return Response(data)


# ---- 6. Supplier Sync -----------------------------------------------------------------
@api_view(["POST"])
def supplier_sync(request):
    """POST /api/sync/supplier/"""
    data = sync_supplier_catalogue()
    return Response(data)


# ---- 7. Dealer Assistant (GenAI) ------------------------------------------------------
@api_view(["POST"])
def assistant_chat(request):
    """
    POST /api/assistant/chat/
    Body: {"session_id": "...", "dealer_id": 7, "message": "..."}
    Response: {"reply": "...", "cited_skus": [...], "tool_calls": [...], "actions": [...]}
    """
    session_id = request.data.get("session_id")
    dealer_id = request.data.get("dealer_id")
    message = (request.data.get("message") or "").strip()

    if not session_id or not message:
        raise ValidationErrorException("session_id and message are required.")

    if dealer_id:
        try:
            dealer_id = int(dealer_id)
        except (ValueError, TypeError):
            raise ValidationErrorException("dealer_id must be a valid integer.")
        if not Dealer.objects.filter(id=dealer_id).exists():
            raise ValidationErrorException(f"Dealer with id {dealer_id} does not exist.")

    result = handle_assistant_turn(session_id=str(session_id), dealer_id=dealer_id, user_message=message)
    return Response(result)


# ---- 8. Forecasting & Reorder (ML) ----------------------------------------------------
def get_lead_times_map():
    lead_path = settings.DATA_DIR / "lead_times.csv"
    if not os.path.exists(lead_path):
        return {}
    m = {}
    with open(lead_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            m[r["sku"]] = int(r["lead_time_weeks"])
    return m


def get_forecast_map():
    forecast_path = settings.BASE_DIR / "ml" / "forecast.csv"
    if not os.path.exists(forecast_path):
        return {}
    m = {}
    with open(forecast_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            sku = r["sku"]
            if sku not in m:
                m[sku] = []
            m[sku].append(
                {
                    "week_start": r["week_start"],
                    "forecast_units": float(r["forecast_units"]),
                }
            )
    return m


def get_sales_history_sigma(sku: str) -> float:
    """Calculate sample standard deviation (ddof=1) of units_sold for most recent 12 weeks."""
    history_path = settings.DATA_DIR / "sales_history.csv"
    if not os.path.exists(history_path):
        return 0.0

    weeks = []
    with open(history_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            if r["sku"] == sku:
                weeks.append((r["week_start"], float(r["units_sold"])))

    if not weeks:
        return 0.0

    # Sort descending by week_start and take last 12 weeks
    weeks.sort(key=lambda x: x[0], reverse=True)
    recent = [w[1] for w in weeks[:12]]

    n = len(recent)
    if n <= 1:
        return 0.0

    mean_val = sum(recent) / n
    variance = sum((x - mean_val) ** 2 for x in recent) / (n - 1)
    return math.sqrt(variance)


@api_view(["GET"])
def forecast_detail(request, sku):
    """GET /api/forecast/{sku}/ -> 4-week forecast or 404"""
    forecast_map = get_forecast_map()
    if sku not in forecast_map:
        raise NotFoundException(f"No forecast found for SKU '{sku}'.")
    return Response({"sku": sku, "forecast": forecast_map[sku]})


@api_view(["GET"])
def reorder_suggestions(request):
    """
    GET /api/reorder-suggestions/ -> 40 forecast SKUs with exact formulas.
    """
    lead_map = get_lead_times_map()
    forecast_map = get_forecast_map()

    # Get live product info from Product table
    products_info = {
        p.sku: {"stock": p.stock, "name": p.name, "price": str(p.price)}
        for p in Product.objects.filter(sku__in=list(lead_map.keys()))
    }

    results = []
    for sku, lead_weeks in lead_map.items():
        p_info = products_info.get(sku, {"stock": 0, "name": sku, "price": "0.00"})
        current_stock = p_info["stock"]
        f_list = forecast_map.get(sku, [])

        # lead_time_demand = sum of forecast_units for first L weeks
        lead_time_demand = sum(
            f_list[i]["forecast_units"] for i in range(min(lead_weeks, len(f_list)))
        )
        lead_time_demand = round(lead_time_demand, 1)

        forecast_4w = round(sum(x["forecast_units"] for x in f_list), 1)
        sigma = get_sales_history_sigma(sku)
        safety_stock = math.ceil(1.65 * sigma * math.sqrt(lead_weeks))
        reorder_point = round(lead_time_demand + safety_stock, 1)
        reorder_qty = max(0, math.ceil(reorder_point - current_stock))

        results.append(
            {
                "sku": sku,
                "product_name": p_info["name"],
                "price": p_info["price"],
                "current_stock": current_stock,
                "lead_time_weeks": lead_weeks,
                "lead_time_demand": lead_time_demand,
                "demand_std_dev": round(sigma, 1),
                "sigma": round(sigma, 1),
                "safety_stock": safety_stock,
                "reorder_point": reorder_point,
                "reorder_qty": reorder_qty,
                "suggested_reorder": reorder_qty,
                "forecast_4w": forecast_4w,
            }
        )

    return Response({"results": results})
