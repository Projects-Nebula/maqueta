from django.urls import path

from .views import (
    PublicBundleAssetView,
    PublicTemplateView,
    editor_view,
    gallery_view,
    home_view,
    template_wizard_view,
)

app_name = "editor"

urlpatterns = [
    path("editor/", editor_view, name="editor"),
    path("gallery/", gallery_view, name="gallery"),
    path("home/", home_view, name="home"),
    path("wizard/", template_wizard_view, name="template-wizard"),
    path("t/<slug:slug>/", PublicTemplateView.as_view(), name="public-template"),
    path("s/<slug:slug>/", PublicBundleAssetView.as_view(), name="public-bundle-root"),
    path(
        "s/<slug:slug>/<path:asset_path>",
        PublicBundleAssetView.as_view(),
        name="public-bundle-asset",
    ),
]
