"""factory-boy factories for test data."""

from datetime import date

import factory

from products.models import Product


class ProductFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Product

    sku = factory.Sequence(lambda n: f"TST-{n:03d}")
    name = factory.LazyAttribute(lambda obj: f"Product {obj.sku}")
    category = "lighting"
    price_paise = 100000
    stock = 1
    updated_at = date(2026, 5, 1)
