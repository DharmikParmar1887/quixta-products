from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Product",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sku", models.CharField(max_length=7, unique=True)),
                ("name", models.CharField(max_length=255)),
                (
                    "category",
                    models.CharField(
                        choices=[("lighting", "Lighting"), ("seating", "Seating"), ("storage", "Storage")],
                        max_length=20,
                    ),
                ),
                ("price_paise", models.PositiveIntegerField()),
                ("stock", models.PositiveIntegerField(default=0)),
                ("updated_at", models.DateField()),
            ],
            options={
                "ordering": ["sku"],
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(("price_paise__gt", 0)), name="product_price_paise_positive"
                    )
                ],
            },
        ),
    ]
