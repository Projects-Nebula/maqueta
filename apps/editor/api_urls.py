from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import UserTemplateViewSet, WizardImageUploadView

router = DefaultRouter()
router.register("", UserTemplateViewSet, basename="user-template")
urlpatterns = [
    path("wizard-images/", WizardImageUploadView.as_view(), name="wizard-image-upload"),
    path(
        "wizard-images/<int:asset_id>/",
        WizardImageUploadView.as_view(),
        name="wizard-image-delete",
    ),
    *router.urls,
]
