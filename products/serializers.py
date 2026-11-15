from datetime import date

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from . import cleaning
from .models import Product

DUPLICATE_SKU_MESSAGE = "A product with this sku already exists."


class CleanedField(serializers.Field):
    """A field that runs one of the cleaning functions on the incoming value.

    This keeps the API on exactly the same rules as the clean_products command.
    Validators (like the unique sku check) run after cleaning, so " lmp-001 "
    is treated as LMP-001.
    """

    def __init__(self, cleaner, **kwargs):
        self.cleaner = cleaner
        super().__init__(**kwargs)

    def to_internal_value(self, data):
        try:
            return self.cleaner(data)
        except cleaning.CleaningError as exc:
            raise serializers.ValidationError(exc.message, code=exc.reason)

    def to_representation(self, value):
        return value.isoformat() if isinstance(value, date) else value


class ProductSerializer(serializers.ModelSerializer):
    sku = CleanedField(
        cleaning.clean_sku,
        validators=[UniqueValidator(queryset=Product.objects.all(), message=DUPLICATE_SKU_MESSAGE)],
    )
    name = CleanedField(cleaning.clean_name)
    category = CleanedField(cleaning.clean_category)
    price_paise = CleanedField(cleaning.clean_price_paise)
    stock = CleanedField(cleaning.clean_stock, default=0)
    updated_at = CleanedField(cleaning.clean_date, default=timezone.localdate)

    class Meta:
        model = Product
        fields = ["sku", "name", "category", "price_paise", "stock", "updated_at"]

    def create(self, validated_data):
        # The unique validator can lose a race with another request; the DB constraint is the backstop.
        try:
            with transaction.atomic():
                return super().create(validated_data)
        except IntegrityError:
            raise serializers.ValidationError({"sku": [DUPLICATE_SKU_MESSAGE]})
