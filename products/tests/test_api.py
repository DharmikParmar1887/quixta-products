import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from products.models import Product
from products.tests.factories import ProductFactory


@pytest.mark.django_db
class ProductListTests(APITestCase):
    url = reverse("product-list")

    def setUp(self):
        for sku in ["LMP-003", "LMP-001", "LMP-002"]:
            ProductFactory(sku=sku, category="lighting")
        for sku in ["STL-002", "STL-001"]:
            ProductFactory(sku=sku, category="seating")
        for sku in ["SHF-001", "SHF-002"]:
            ProductFactory(sku=sku, category="storage")

    def test_pages_of_five_ordered_by_sku(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.json()
        self.assertEqual(body["count"], 7)
        self.assertIsNone(body["previous"])
        self.assertIsNotNone(body["next"])
        self.assertEqual(
            [p["sku"] for p in body["results"]],
            ["LMP-001", "LMP-002", "LMP-003", "SHF-001", "SHF-002"],
        )

        page_two = self.client.get(self.url, {"page": 2}).json()
        self.assertEqual([p["sku"] for p in page_two["results"]], ["STL-001", "STL-002"])

    def test_result_shape(self):
        first = self.client.get(self.url).json()["results"][0]
        self.assertEqual(
            first,
            {
                "sku": "LMP-001",
                "name": "Product LMP-001",
                "category": "lighting",
                "price_paise": 100000,
                "stock": 1,
                "updated_at": "2026-05-01",
            },
        )

    def test_filter_by_category_returns_only_that_category(self):
        body = self.client.get(self.url, {"category": "seating"}).json()
        self.assertEqual(body["count"], 2)
        self.assertEqual({p["category"] for p in body["results"]}, {"seating"})


@pytest.mark.django_db
class ProductDetailTests(APITestCase):
    def test_returns_one_product(self):
        ProductFactory(sku="LMP-001")
        response = self.client.get(reverse("product-detail", args=["LMP-001"]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["sku"], "LMP-001")

    def test_unknown_sku_is_404(self):
        response = self.client.get(reverse("product-detail", args=["LMP-999"]))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


@pytest.mark.django_db
class ProductCreateTests(APITestCase):
    url = reverse("product-list")
    valid = {"sku": "LMP-010", "name": "Reading lamp", "category": "lighting", "price_paise": 450000, "stock": 3}

    def post(self, **changes):
        return self.client.post(self.url, {**self.valid, **changes}, format="json")

    def test_valid_product_is_created(self):
        response = self.post()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.json(), {**self.valid, "updated_at": timezone.localdate().isoformat()})
        self.assertTrue(Product.objects.filter(sku="LMP-010").exists())

    def test_values_are_cleaned_like_the_command(self):
        response = self.post(sku=" lmp-010 ", name="  Reading   lamp ", category="Lighting")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        body = response.json()
        self.assertEqual((body["sku"], body["name"], body["category"]), ("LMP-010", "Reading lamp", "lighting"))

    def test_stock_defaults_to_zero(self):
        data = {k: v for k, v in self.valid.items() if k != "stock"}
        response = self.client.post(self.url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.json()["stock"], 0)

    def test_bad_category_is_400_with_category_key(self):
        response = self.post(category="decor")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("category", response.json())
        self.assertFalse(Product.objects.exists())

    def test_duplicate_sku_is_400_with_sku_key(self):
        ProductFactory(sku="LMP-010")
        for sku in ["LMP-010", "lmp-010"]:
            with self.subTest(sku=sku):
                response = self.post(sku=sku)
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn("sku", response.json())

    def test_every_failing_field_gets_a_key(self):
        response = self.post(sku="BOX-01", name="  ", price_paise=0, stock=-1, updated_at="2026-13-01")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(set(response.json()), {"sku", "name", "price_paise", "stock", "updated_at"})

    def test_missing_required_fields(self):
        response = self.client.post(self.url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(set(response.json()), {"sku", "name", "category", "price_paise"})
