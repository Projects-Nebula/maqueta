from django.urls import path

from .views import (
    CheckoutView,
    DownloadView,
    StripeWebhookView,
    SuccessView,
    checkout_cancel_view,
    products_view,
)

app_name = "storefront"

urlpatterns = [
    path("productos/", products_view, name="products"),
    path("comprar/<int:product_id>/", CheckoutView.as_view(), name="checkout"),
    path("gracias/", SuccessView.as_view(), name="success"),
    path("cancelado/", checkout_cancel_view, name="checkout-cancel"),
    path("webhooks/stripe/", StripeWebhookView.as_view(), name="stripe-webhook"),
    path("descargas/<str:token>/", DownloadView.as_view(), name="download"),
]
