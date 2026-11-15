from datetime import date

from django.test import SimpleTestCase

from products import cleaning
from products.cleaning import CleaningError, CleanProduct


class CleanValueTests(SimpleTestCase):
    def assertRejects(self, cleaner, raw, reason):
        with self.assertRaises(CleaningError) as ctx:
            cleaner(raw)
        self.assertEqual(ctx.exception.reason, reason)

    def test_price_in_rupees_becomes_paise(self):
        self.assertEqual(cleaning.clean_price("₹6,500"), 650000)
        self.assertEqual(cleaning.clean_price("14,999.50"), 1499950)
        self.assertEqual(cleaning.clean_price(" 2,400 "), 240000)
        self.assertEqual(cleaning.clean_price("₹10,250.75"), 1025075)

    def test_bad_prices_are_rejected(self):
        for raw in ["free", "0", "0.00", "-5", "1.234", "", "1.2.3"]:
            with self.subTest(raw=raw):
                self.assertRejects(cleaning.clean_price, raw, cleaning.INVALID_PRICE)

    def test_name_is_trimmed_and_inner_spaces_squashed(self):
        self.assertEqual(cleaning.clean_name("  Birch   desk lamp "), "Birch desk lamp")
        self.assertRejects(cleaning.clean_name, "   ", cleaning.MISSING_NAME)

    def test_sku_is_trimmed_and_uppercased(self):
        self.assertEqual(cleaning.clean_sku(" lmp-002 "), "LMP-002")
        for raw in ["BOX-01", "LMPP-001", "LMP001", ""]:
            with self.subTest(raw=raw):
                self.assertRejects(cleaning.clean_sku, raw, cleaning.INVALID_SKU)

    def test_category_is_lowercased(self):
        self.assertEqual(cleaning.clean_category("SEATING "), "seating")
        self.assertRejects(cleaning.clean_category, "decor", cleaning.UNKNOWN_CATEGORY)

    def test_stock(self):
        self.assertEqual(cleaning.clean_stock(""), 0)
        self.assertEqual(cleaning.clean_stock(" 7 "), 7)
        for raw in ["-2", "3.5", "abc"]:
            with self.subTest(raw=raw):
                self.assertRejects(cleaning.clean_stock, raw, cleaning.INVALID_STOCK)

    def test_date(self):
        self.assertEqual(cleaning.clean_date(" 2026-05-02 "), date(2026, 5, 2))
        for raw in ["2026-13-01", "2026-02-30", "20260502", "2026-5-2", ""]:
            with self.subTest(raw=raw):
                self.assertRejects(cleaning.clean_date, raw, cleaning.INVALID_DATE)


class CleanRowTests(SimpleTestCase):
    def test_first_failing_column_decides_the_reason(self):
        row = {"sku": "BAD", "name": "", "category": "decor", "price": "free", "stock": "x", "updated_at": "nope"}
        result = cleaning.clean_rows([(2, row)])
        self.assertEqual(result.rejects, [(2, cleaning.INVALID_SKU)])


class DropDuplicatesTests(SimpleTestCase):
    def product(self, line, updated_at, sku="LMP-001"):
        return CleanProduct(line, sku, "Lamp", "lighting", 100, 1, updated_at)

    def test_latest_date_wins(self):
        newer = self.product(2, date(2026, 5, 9))
        older = self.product(3, date(2026, 5, 1))
        kept, dropped = cleaning.drop_duplicates([newer, older])
        self.assertEqual(kept, [newer])
        self.assertEqual(dropped, 1)

    def test_same_date_keeps_the_lower_row(self):
        first = self.product(2, date(2026, 5, 6))
        second = self.product(5, date(2026, 5, 6))
        kept, dropped = cleaning.drop_duplicates([first, second])
        self.assertEqual(kept, [second])
        self.assertEqual(dropped, 1)
