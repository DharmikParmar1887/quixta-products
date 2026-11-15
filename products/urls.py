from django.urls import path

from .views import ProductDetailView, ProductListCreateView

urlpatterns = [
    path("products/", ProductListCreateView.as_view(), name="product-list"),
    path("products/<str:sku>/", ProductDetailView.as_view(), name="product-detail"),
]
