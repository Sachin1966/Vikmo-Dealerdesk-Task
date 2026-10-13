import csv
from decimal import Decimal
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Dealer, Product


class Command(BaseCommand):
    help = "Load catalogue.csv and dealers.csv into PostgreSQL. Idempotent and safe to run multiple times."

    def add_arguments(self, parser):
        parser.add_argument(
            "--clean",
            action="store_true",
            help="Remove non-seed records (e.g. mock sync products and test orders) before seeding.",
        )

    def handle(self, *args, **options):
        data_dir = getattr(settings, "DATA_DIR", settings.BASE_DIR / "data")
        catalogue_path = Path(data_dir) / "catalogue.csv"
        dealers_path = Path(data_dir) / "dealers.csv"

        if not catalogue_path.exists():
            self.stdout.write(self.style.ERROR(f"Catalogue file not found: {catalogue_path}"))
            return

        if not dealers_path.exists():
            self.stdout.write(self.style.ERROR(f"Dealers file not found: {dealers_path}"))
            return

        if options.get("clean"):
            from core.models import OrderItem, Order, OrderDailySequence, IdempotencyRecord
            self.stdout.write("Cleaning orders, sequences, and non-seed records...")
            with transaction.atomic():
                OrderItem.objects.all().delete()
                Order.objects.all().delete()
                OrderDailySequence.objects.all().delete()
                IdempotencyRecord.objects.all().delete()
                with open(catalogue_path, mode="r", encoding="utf-8") as f:
                    v_skus = {r["sku"].strip() for r in csv.DictReader(f)}
                Product.objects.exclude(sku__in=v_skus).delete()
                with open(dealers_path, mode="r", encoding="utf-8") as f:
                    v_dealers = {r["dealer_code"].strip() for r in csv.DictReader(f)}
                Dealer.objects.exclude(dealer_code__in=v_dealers).delete()
            self.stdout.write(self.style.SUCCESS("Clean complete."))

        # 1. Seed Catalogue
        self.stdout.write("Seeding products from catalogue.csv...")
        products_created = 0
        products_updated = 0

        with open(catalogue_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            with transaction.atomic():
                existing_products = {p.sku: p for p in Product.objects.all().select_for_update()}

                for row in reader:
                    sku = row["sku"].strip()
                    name = row["name"].strip()
                    category = row["category"].strip()
                    brand = row["brand"].strip()
                    vehicle_fitment = row["vehicle_fitment"].strip()
                    price = Decimal(row["price"].strip())
                    stock_qty = int(row["stock"].strip())
                    description = row.get("description", "").strip()

                    if sku not in existing_products:
                        Product.objects.create(
                            sku=sku,
                            name=name,
                            category=category,
                            brand=brand,
                            vehicle_fitment=vehicle_fitment,
                            price=price,
                            stock=stock_qty,
                            description=description,
                        )
                        products_created += 1
                    else:
                        # Idempotent re-run: preserve live stock, update metadata if needed
                        p = existing_products[sku]
                        p.name = name
                        p.category = category
                        p.brand = brand
                        p.vehicle_fitment = vehicle_fitment
                        p.price = price
                        p.description = description
                        # Note: stock is preserved to prevent resetting live inventory on repeat runs
                        p.save(
                            update_fields=[
                                "name",
                                "category",
                                "brand",
                                "vehicle_fitment",
                                "price",
                                "description",
                                "updated_at",
                            ]
                        )
                        products_updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Catalogue seeding complete: {products_created} created, {products_updated} updated."
            )
        )

        # 2. Seed Dealers
        self.stdout.write("Seeding dealers from dealers.csv...")
        dealers_created = 0
        dealers_updated = 0

        with open(dealers_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            with transaction.atomic():
                existing_dealers = {d.dealer_code: d for d in Dealer.objects.all().select_for_update()}

                for row in reader:
                    dealer_code = row["dealer_code"].strip()
                    name = row["name"].strip()
                    city = row.get("city", "").strip()
                    phone = row.get("phone", "").strip()
                    email = row.get("email", "").strip()
                    gstin = row.get("gstin", "").strip()
                    credit_limit = Decimal(row.get("credit_limit", "0.00").strip() or "0.00")

                    if dealer_code not in existing_dealers:
                        Dealer.objects.create(
                            dealer_code=dealer_code,
                            name=name,
                            city=city,
                            phone=phone,
                            email=email,
                            gstin=gstin,
                            credit_limit=credit_limit,
                        )
                        dealers_created += 1
                    else:
                        d = existing_dealers[dealer_code]
                        d.name = name
                        d.city = city
                        d.phone = phone
                        d.email = email
                        d.gstin = gstin
                        d.credit_limit = credit_limit
                        d.save(
                            update_fields=[
                                "name",
                                "city",
                                "phone",
                                "email",
                                "gstin",
                                "credit_limit",
                                "updated_at",
                            ]
                        )
                        dealers_updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Dealers seeding complete: {dealers_created} created, {dealers_updated} updated."
            )
        )
