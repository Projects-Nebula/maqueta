from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import DisconnectView, ProductLinkViewSet, ProductListView

app_name = "hotmart_api"

router = SimpleRouter()
router.register("links", ProductLinkViewSet, basename="link")

urlpatterns = [
    path("disconnect/", DisconnectView.as_view(), name="disconnect"),
    path("products/", ProductListView.as_view(), name="products"),
    path("", include(router.urls)),
]
