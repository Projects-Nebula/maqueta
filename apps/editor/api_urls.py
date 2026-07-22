from rest_framework.routers import DefaultRouter

from .views import UserTemplateViewSet

router = DefaultRouter()
router.register("", UserTemplateViewSet, basename="user-template")
urlpatterns = router.urls
