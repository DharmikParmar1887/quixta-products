from django.db import models

from .cleaning import CATEGORIES


class Product(models.Model):
    CATEGORY_CHOICES = [(name, name.title()) for name in CATEGORIES]

    sku = models.CharField(max_length=7, unique=True)
    name = models.CharField(max_length=255)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    price_paise = models.PositiveIntegerField()
    stock = models.PositiveIntegerField(default=0)
    updated_at = models.DateField()

    class Meta:
        ordering = ["sku"]
        constraints = [
            models.CheckConstraint(condition=models.Q(price_paise__gt=0), name="product_price_paise_positive"),
        ]

    def __str__(self):
        return f"{self.sku} {self.name}"
