from rest_framework.routers import DefaultRouter

from .views import UserPaletteViewSet

router = DefaultRouter()
router.register("", UserPaletteViewSet, basename="user-palette")

urlpatterns = router.urls
