import csv
import json
import tempfile
from io import StringIO
from pathlib import Path

import pytest
from django.conf import settings
from django.core.management import CommandError, call_command
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from products.models import Product
from products.tests.factories import ProductFactory

PRODUCTS_CSV = settings.BASE_DIR / "products.csv"


@pytest.mark.django_db
class CleanProductsCommandTests(TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.rejects_path = Path(tmp.name) / "rejects.csv"

    def run_command(self):
        out = StringIO()
        call_command("clean_products", str(PRODUCTS_CSV), rejects=str(self.rejects_path), stdout=out)
        return json.loads(out.getvalue().strip().splitlines()[-1])

    def test_summary_for_products_csv(self):
        summary = self.run_command()
        self.assertEqual(
            summary,
            {
                "loaded": 10,
                "rejected": {
                    "invalid_sku": 1,
                    "missing_name": 1,
                    "unknown_category": 1,
                    "invalid_price": 2,
                    "invalid_stock": 3,
                    "invalid_date": 1,
                },
                "duplicatesDropped": 3,
            },
        )
        self.assertEqual(Product.objects.count(), 10)

    def test_rejects_csv_lists_line_and_reason(self):
        self.run_command()
        with self.rejects_path.open(newline="") as fh:
            rows = list(csv.reader(fh))
        self.assertEqual(rows[0], ["line", "reason"])
        self.assertEqual(
            rows[1:],
            [
                ["7", "invalid_price"],
                ["8", "invalid_stock"],
                ["9", "missing_name"],
                ["11", "invalid_stock"],
                ["12", "invalid_price"],
                ["13", "invalid_sku"],
                ["15", "unknown_category"],
                ["18", "invalid_date"],
                ["22", "invalid_stock"],
            ],
        )

    def test_duplicates_keep_the_right_row(self):
        self.run_command()
        # Latest date wins.
        self.assertEqual(Product.objects.get(sku="LMP-001").price_paise, 820000)
        # The later row has an older date, so the first row stays.
        self.assertEqual(Product.objects.get(sku="STL-001").price_paise, 1200000)
        # Same date: the lower row in the file wins.
        self.assertEqual(Product.objects.get(sku="SHF-001").price_paise, 1850000)

    def test_cleaned_values_are_stored(self):
        self.run_command()
        lamp = Product.objects.get(sku="LMP-002")
        self.assertEqual(lamp.name, "Birch desk lamp")
        self.assertEqual(lamp.category, "lighting")
        self.assertEqual(lamp.price_paise, 650000)
        self.assertEqual(Product.objects.get(sku="STL-002").stock, 0)

    def test_running_twice_leaves_the_table_the_same(self):
        first_summary = self.run_command()
        first = list(Product.objects.order_by("sku").values())
        second_summary = self.run_command()
        second = list(Product.objects.order_by("sku").values())
        self.assertEqual(first_summary, second_summary)
        self.assertEqual(Product.objects.count(), 10)
        self.assertEqual(first, second)

    def test_existing_product_is_updated_and_others_are_kept(self):
        ProductFactory(sku="LMP-001", name="Old name", price_paise=1)
        ProductFactory(sku="API-001")
        self.run_command()
        lamp = Product.objects.get(sku="LMP-001")
        self.assertEqual((lamp.name, lamp.price_paise), ("Maple lamp", 820000))
        self.assertTrue(Product.objects.filter(sku="API-001").exists())
        self.assertEqual(Product.objects.count(), 11)

    def test_all_rows_are_saved_in_one_insert_query(self):
        with CaptureQueriesContext(connection) as ctx:
            self.run_command()
        inserts = [q["sql"] for q in ctx.captured_queries if q["sql"].lstrip().upper().startswith("INSERT")]
        self.assertEqual(len(inserts), 1)

    def test_missing_file_is_a_clear_error(self):
        with self.assertRaises(CommandError):
            call_command("clean_products", "does-not-exist.csv", rejects=str(self.rejects_path), stdout=StringIO())
