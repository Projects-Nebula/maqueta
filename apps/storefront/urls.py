from django.urls import path

from .views import (
    BoldWebhookView,
    BraintreeWebhookView,
    CheckoutView,
    DownloadView,
    EpaycoWebhookView,
    MercadoPagoWebhookView,
    PayPalWebhookView,
    PayUWebhookView,
    StripeWebhookView,
    SuccessView,
    WompiWebhookView,
    checkout_cancel_view,
    payment_config_view,
    payu_redirect_view,
    products_view,
)

app_name = "storefront"

urlpatterns = [
    path("productos/", products_view, name="products"),
    path("config/", payment_config_view, name="payment-config"),
    path("comprar/<int:product_id>/<str:gateway>/", CheckoutView.as_view(), name="checkout"),
    # Legacy, pre-multi-gateway buy buttons (baked into a UserTemplate's
    # saved state from before this URL required a gateway segment) still
    # point at this shape — CheckoutView falls back to the seller's first
    # enabled gateway rather than 404ing an already-published page's button.
    path("comprar/<int:product_id>/", CheckoutView.as_view(), name="checkout-legacy"),
    path("pagar/payu/redirect/", payu_redirect_view, name="payu-redirect"),
    path("gracias/", SuccessView.as_view(), name="success"),
    path("cancelado/", checkout_cancel_view, name="checkout-cancel"),
    path("webhooks/stripe/", StripeWebhookView.as_view(), name="webhook-stripe"),
    path("webhooks/mercadopago/", MercadoPagoWebhookView.as_view(), name="webhook-mercadopago"),
    path("webhooks/paypal/", PayPalWebhookView.as_view(), name="webhook-paypal"),
    path("webhooks/braintree/", BraintreeWebhookView.as_view(), name="webhook-braintree"),
    path("webhooks/wompi/", WompiWebhookView.as_view(), name="webhook-wompi"),
    path("webhooks/payu/", PayUWebhookView.as_view(), name="webhook-payu"),
    path("webhooks/epayco/", EpaycoWebhookView.as_view(), name="webhook-epayco"),
    path("webhooks/bold/", BoldWebhookView.as_view(), name="webhook-bold"),
    path("descargas/<str:token>/", DownloadView.as_view(), name="download"),
]
