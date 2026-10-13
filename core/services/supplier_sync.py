import logging
import math
import re
import time
from datetime import datetime
from decimal import Decimal, InvalidOperation
from django.conf import settings
from django.db import transaction
import requests

from core.exceptions import SupplierUnavailableException
from core.models import Product

logger = logging.getLogger(__name__)

PRICE_REGEX = re.compile(r"^\d+(\.\d{1,2})?$")
MAX_ATTEMPTS = 5


def parse_iso_datetime(dt_str: str) -> datetime:
    if not dt_str:
        return datetime.min
    try:
        # Handle trailing Z
        clean_str = dt_str.replace("Z", "+00:00")
        return datetime.fromisoformat(clean_str)
    except Exception:
        return datetime.min


def validate_supplier_item(item: dict):
    """Validate item fields. Returns (is_valid, reason, clean_price_dec)."""
    sku = item.get("sku")
    if not sku or not isinstance(sku, str) or not sku.strip():
        return False, "missing or empty sku", None

    raw_price = item.get("price")
    if raw_price is None or not isinstance(raw_price, (str, int, float)):
        return False, "invalid price", None

    str_price = str(raw_price).strip()
    if not PRICE_REGEX.match(str_price):
        return False, "invalid price", None

    try:
        dec_price = Decimal(str_price)
    except InvalidOperation:
        return False, "invalid price", None

    if dec_price <= 0:
        return False, "invalid price", None

    return True, None, dec_price


def sync_supplier_catalogue() -> dict:
    """Run full catalogue synchronization against the external supplier API."""
    base_url = getattr(settings, "SUPPLIER_API_URL", "http://127.0.0.1:8099").rstrip("/")
    api_key = getattr(settings, "SUPPLIER_API_KEY", "")

    url = f"{base_url}/v1/products"
    headers = {"X-Api-Key": api_key}

    cursor = None
    pages_fetched = 0
    requests_made = 0
    all_raw_items = []

    # 1. Fetch all pages with retry logic
    while True:
        params = {"limit": 20}
        if cursor:
            params["cursor"] = cursor

        success = False
        last_error = None

        for attempt in range(1, MAX_ATTEMPTS + 1):
            requests_made += 1
            try:
                resp = requests.get(url, params=params, headers=headers, timeout=20)
                if resp.status_code == 200:
                    data = resp.json()
                    pages_fetched += 1
                    items = data.get("items", [])
                    all_raw_items.extend(items)
                    cursor = data.get("next_cursor")
                    success = True
                    break
                elif resp.status_code == 401:
                    logger.error("Supplier rejected API key (401)")
                    raise SupplierUnavailableException("Supplier authentication failed.")
                elif resp.status_code == 429:
                    retry_after = resp.headers.get("Retry-After", "1")
                    try:
                        wait_sec = max(1, math.ceil(float(retry_after)))
                    except ValueError:
                        wait_sec = 1
                    logger.warning(f"Supplier rate-limited (429), waiting {wait_sec}s")
                    time.sleep(wait_sec)
                elif resp.status_code >= 500:
                    logger.warning(f"Supplier server error ({resp.status_code}), attempt {attempt}/{MAX_ATTEMPTS}")
                    time.sleep(0.5)
                else:
                    logger.error(f"Supplier returned unexpected status {resp.status_code}")
                    time.sleep(0.5)
            except requests.RequestException as e:
                last_error = e
                logger.warning(f"Supplier connection error: {e}, attempt {attempt}/{MAX_ATTEMPTS}")
                time.sleep(0.5)

        if not success:
            logger.error(f"Failed to fetch supplier page after {MAX_ATTEMPTS} attempts: {last_error}")
            raise SupplierUnavailableException("Supplier API could not be fetched after max retries.")

        if not cursor:
            break

    # 2. Filter invalid items and collect rejects
    valid_items = []
    rejected = []

    for it in all_raw_items:
        is_valid, reason, dec_price = validate_supplier_item(it)
        if not is_valid:
            rejected.append(
                {
                    "supplier_sku": it.get("supplier_sku", ""),
                    "reason": reason,
                }
            )
        else:
            it["_parsed_price"] = dec_price
            it["_parsed_dt"] = parse_iso_datetime(it.get("updated_at", ""))
            valid_items.append(it)

    # 3. Deduplicate valid items across pages by latest updated_at
    latest_by_sku = {}
    for it in valid_items:
        sku = it["sku"].strip()
        if sku not in latest_by_sku:
            latest_by_sku[sku] = it
        else:
            if it["_parsed_dt"] > latest_by_sku[sku]["_parsed_dt"]:
                latest_by_sku[sku] = it

    # 4. Atomically apply changes to database without touching local stock
    created_count = 0
    updated_count = 0
    unchanged_count = 0

    with transaction.atomic():
        existing_products = {
            p.sku: p
            for p in Product.objects.filter(sku__in=list(latest_by_sku.keys())).select_for_update()
        }

        for sku, it in latest_by_sku.items():
            name = (it.get("name") or "").strip()
            category = (it.get("category") or "").strip()
            brand = (it.get("brand") or "").strip()
            vehicle_fitment = (it.get("vehicle_fitment") or "").strip()
            description = it.get("description") or ""
            price = it["_parsed_price"]

            if sku not in existing_products:
                Product.objects.create(
                    sku=sku,
                    name=name,
                    category=category,
                    brand=brand,
                    vehicle_fitment=vehicle_fitment,
                    price=price,
                    stock=0,  # New products start with stock 0
                    description=description,
                )
                created_count += 1
            else:
                p = existing_products[sku]
                # Check if any catalogue field changed
                differs = (
                    p.name != name
                    or p.category != category
                    or p.brand != brand
                    or p.vehicle_fitment != vehicle_fitment
                    or p.description != description
                    or p.price != price
                )

                if differs:
                    p.name = name
                    p.category = category
                    p.brand = brand
                    p.vehicle_fitment = vehicle_fitment
                    p.description = description
                    p.price = price
                    # Stock is intentionally NOT modified
                    p.save(
                        update_fields=[
                            "name",
                            "category",
                            "brand",
                            "vehicle_fitment",
                            "description",
                            "price",
                            "updated_at",
                        ]
                    )
                    updated_count += 1
                else:
                    unchanged_count += 1

    return {
        "created": created_count,
        "updated": updated_count,
        "unchanged": unchanged_count,
        "rejected": rejected,
        "pages_fetched": pages_fetched,
        "requests_made": requests_made,
    }
