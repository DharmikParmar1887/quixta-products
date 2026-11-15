from django.shortcuts import get_object_or_404
from rest_framework import generics

from .models import Product
from .serializers import ProductSerializer


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
