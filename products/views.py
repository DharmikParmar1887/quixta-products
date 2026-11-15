from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import generics

from .cleaning import CATEGORIES
from .models import Product
from .serializers import ProductSerializer

CATEGORY_PARAM = openapi.Parameter(
    "category",
    openapi.IN_QUERY,
    description="Only products in this category.",
    type=openapi.TYPE_STRING,
    enum=list(CATEGORIES),
)


@method_decorator(name="get", decorator=swagger_auto_schema(manual_parameters=[CATEGORY_PARAM]))
class ProductListCreateView(generics.ListCreateAPIView):
    """GET: products ordered by sku, 5 per page, optional ?category=. POST: create one."""

    serializer_class = ProductSerializer

    def get_queryset(self):
        queryset = Product.objects.order_by("sku")
        category = self.request.query_params.get("category")
        if category:
            queryset = queryset.filter(category=category.strip().lower())
        return queryset


class ProductDetailView(generics.RetrieveAPIView):
    serializer_class = ProductSerializer
    queryset = Product.objects.all()

    def get_object(self):
        return get_object_or_404(self.get_queryset(), sku=self.kwargs["sku"].strip().upper())
