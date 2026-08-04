from rest_framework.routers import DefaultRouter

from .views import BundleViewSet

router = DefaultRouter()
router.register("", BundleViewSet, basename="site-bundle")

urlpatterns = router.urls
