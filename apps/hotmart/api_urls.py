from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import (
    CredentialsView,
    DisconnectView,
    ProductLandingGenerateView,
    ProductLinkViewSet,
    ProductListView,
)

app_name = "hotmart_api"

router = SimpleRouter()
router.register("links", ProductLinkViewSet, basename="link")

urlpatterns = [
    path("credentials/", CredentialsView.as_view(), name="credentials"),
    path("disconnect/", DisconnectView.as_view(), name="disconnect"),
    path("products/", ProductListView.as_view(), name="products"),
    path(
        "products/<str:product_id>/generate/",
        ProductLandingGenerateView.as_view(),
        name="product-landing-generate",
    ),
    path("", include(router.urls)),
]
