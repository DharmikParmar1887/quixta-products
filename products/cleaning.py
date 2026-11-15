"""Cleaning rules for the supplier product list.

This module is plain Python with no Django imports, so the same rules are used
by the `clean_products` command and by the API serializer, and can be unit
tested on their own.

Each `clean_*` function takes the raw value and either returns the cleaned
value or raises `CleaningError` carrying the reject reason.
"""

import csv
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

CATEGORIES = ("lighting", "seating", "storage")
COLUMNS = ("sku", "name", "category", "price", "stock", "updated_at")

# Reject reasons, in the same order the columns are checked.
INVALID_SKU = "invalid_sku"
MISSING_NAME = "missing_name"
UNKNOWN_CATEGORY = "unknown_category"
INVALID_PRICE = "invalid_price"
INVALID_STOCK = "invalid_stock"
INVALID_DATE = "invalid_date"
REASONS = (
    INVALID_SKU,
    MISSING_NAME,
    UNKNOWN_CATEGORY,
    INVALID_PRICE,
    INVALID_STOCK,
    INVALID_DATE,
)

# [0-9] instead of \d so non-ASCII digits are not accepted.
SKU_RE = re.compile(r"[A-Z]{3}-[0-9]{3}")
RUPEES_RE = re.compile(r"[0-9]+(\.[0-9]{1,2})?")
WHOLE_NUMBER_RE = re.compile(r"[0-9]+")
DATE_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


class CleaningError(ValueError):
    def __init__(self, reason, message):
        super().__init__(message)
        self.reason = reason
        self.message = message


def _text(raw):
    return "" if raw is None else str(raw)


def clean_sku(raw):
    value = _text(raw).strip().upper()
    if not SKU_RE.fullmatch(value):
        raise CleaningError(INVALID_SKU, "Must be three letters, a dash and three digits, like LMP-001.")
    return value


def clean_name(raw):
    value = re.sub(r" {2,}", " ", _text(raw).strip())
    if not value:
        raise CleaningError(MISSING_NAME, "Name cannot be empty.")
    return value


def clean_category(raw):
    value = _text(raw).strip().lower()
    if value not in CATEGORIES:
        raise CleaningError(UNKNOWN_CATEGORY, f"Must be one of: {', '.join(CATEGORIES)}.")
    return value


def clean_price(raw):
    """Rupees as text (e.g. "₹6,500" or "14,999.50") -> integer paise."""
    value = re.sub(r"[\s₹,]", "", _text(raw))
    if not RUPEES_RE.fullmatch(value):
        raise CleaningError(INVALID_PRICE, "Must be a number in rupees with up to 2 decimal places.")
    # Decimal, not float, so 14999.50 * 100 is exactly 1499950.
    paise = int(Decimal(value) * 100)
    if paise <= 0:
        raise CleaningError(INVALID_PRICE, "Price must be above 0.")
    return paise


def clean_price_paise(raw):
    """The API takes the price already in paise, so it must be a whole number above 0."""
    value = _text(raw).strip()
    if not WHOLE_NUMBER_RE.fullmatch(value) or int(value) <= 0:
        raise CleaningError(INVALID_PRICE, "Must be a whole number of paise above 0.")
    return int(value)


def clean_stock(raw):
    value = _text(raw).strip()
    if value == "":
        return 0
    if not WHOLE_NUMBER_RE.fullmatch(value):
        raise CleaningError(INVALID_STOCK, "Must be a whole number, 0 or more.")
    return int(value)


def clean_date(raw):
    value = _text(raw).strip()
    # fromisoformat alone also accepts forms like 20260502, so check the shape first.
    if not DATE_RE.fullmatch(value):
        raise CleaningError(INVALID_DATE, "Must be a real date in YYYY-MM-DD format.")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise CleaningError(INVALID_DATE, "Must be a real date in YYYY-MM-DD format.") from None


@dataclass(frozen=True)
class CleanProduct:
    line: int
    sku: str
    name: str
    category: str
    price_paise: int
    stock: int
    updated_at: date


def clean_row(row, line):
    """Clean one CSV row. Columns are checked in order; the first failure wins."""
    return CleanProduct(
        line=line,
        sku=clean_sku(row.get("sku")),
        name=clean_name(row.get("name")),
        category=clean_category(row.get("category")),
        price_paise=clean_price(row.get("price")),
        stock=clean_stock(row.get("stock")),
        updated_at=clean_date(row.get("updated_at")),
    )


def drop_duplicates(products):
    """Keep one product per sku: the latest updated_at, ties going to the lower line.

    `products` must be in file order. Returns (kept, number_dropped).
    """
    latest = {}
    for product in products:
        current = latest.get(product.sku)
        # >= so a later line with the same date replaces the earlier one.
        if current is None or product.updated_at >= current.updated_at:
            latest[product.sku] = product
    kept = sorted(latest.values(), key=lambda p: p.sku)
    return kept, len(products) - len(kept)


@dataclass
class CleanResult:
    kept: list
    rejects: list = field(default_factory=list)  # (line, reason) pairs
    duplicates_dropped: int = 0

    @property
    def rejected_counts(self):
        counts = Counter(reason for _, reason in self.rejects)
        return {reason: counts[reason] for reason in REASONS if counts[reason]}


def clean_rows(rows):
    """Clean (line, row_dict) pairs and drop duplicate skus."""
    valid, rejects = [], []
    for line, row in rows:
        try:
            valid.append(clean_row(row, line))
        except CleaningError as exc:
            rejects.append((line, exc.reason))
    kept, dropped = drop_duplicates(valid)
    return CleanResult(kept=kept, rejects=rejects, duplicates_dropped=dropped)


def read_rows(fh):
    """Yield (line_number, row_dict) from an open CSV file. The header is line 1.

    Uses csv.reader rather than DictReader so line numbers stay correct when the
    file has blank lines or quoted values that span lines.
    """
    reader = csv.reader(fh)
    header = next(reader, None)
    if header is None:
        raise ValueError("The CSV file is empty.")
    header = [name.strip() for name in header]
    missing = [name for name in COLUMNS if name not in header]
    if missing:
        raise ValueError(f"The CSV file is missing columns: {', '.join(missing)}")

    next_line = reader.line_num + 1
    for values in reader:
        line, next_line = next_line, reader.line_num + 1
        if not any(value.strip() for value in values):
            continue
        yield line, dict(zip(header, values))
