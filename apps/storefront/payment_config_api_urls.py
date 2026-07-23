from rest_framework.routers import DefaultRouter

from .views import PaymentGatewayConfigViewSet

router = DefaultRouter()
router.register("", PaymentGatewayConfigViewSet, basename="payment-gateway-config")
urlpatterns = router.urls
