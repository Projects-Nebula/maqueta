from django.urls import path

from .views import products_view

app_name = "storefront"

urlpatterns = [
    path("productos/", products_view, name="products"),
]
