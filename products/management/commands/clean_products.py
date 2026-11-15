import csv
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from products.cleaning import clean_rows, read_rows
from products.models import Product

UPSERT_FIELDS = ["name", "category", "price_paise", "stock", "updated_at"]


class Command(BaseCommand):
    help = "Clean a supplier products CSV, load the valid rows and write rejects.csv."

    def add_arguments(self, parser):
        parser.add_argument("csv_path", help="Path to the products CSV file.")
        parser.add_argument(
            "--rejects",
            default="rejects.csv",
            help="Where to write the rejected rows (default: rejects.csv in the current folder).",
        )

    def handle(self, *args, **options):
        csv_path = Path(options["csv_path"])
        rejects_path = Path(options["rejects"])

        try:
            with csv_path.open(newline="", encoding="utf-8-sig") as fh:
                result = clean_rows(read_rows(fh))
        except FileNotFoundError:
            raise CommandError(f"File not found: {csv_path}")
        except ValueError as exc:
            raise CommandError(str(exc))

        self.save(result.kept)
        self.write_rejects(rejects_path, result.rejects)

        summary = {
            "loaded": len(result.kept),
            "rejected": result.rejected_counts,
            "duplicatesDropped": result.duplicates_dropped,
        }
        self.stdout.write(json.dumps(summary))

    @transaction.atomic
    def save(self, products):
        # One bulk upsert by sku (INSERT ... ON CONFLICT (sku) DO UPDATE) instead of
        # a SELECT plus INSERT/UPDATE per row. Running the same file again changes nothing.
        Product.objects.bulk_create(
            [
                Product(
                    sku=product.sku,
                    name=product.name,
                    category=product.category,
                    price_paise=product.price_paise,
                    stock=product.stock,
                    updated_at=product.updated_at,
                )
                for product in products
            ],
            update_conflicts=True,
            unique_fields=["sku"],
            update_fields=UPSERT_FIELDS,
        )

    def write_rejects(self, path, rejects):
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["line", "reason"])
            writer.writerows(rejects)
