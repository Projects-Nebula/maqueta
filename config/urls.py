"""Root URL configuration."""

from django.conf import settings
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from django.views.static import serve as serve_media


def healthcheck(_request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz/", healthcheck, name="healthz"),
    path("", include("apps.editor.urls")),
    path("", include("apps.accounts.urls")),
    path("api/ai/", include("apps.ai_assistant.urls")),
    path("api/projects/", include("apps.projects.urls")),
    path("api/user-templates/", include("apps.editor.api_urls")),
    path("", include("apps.storefront.urls")),
    path("api/products/", include("apps.storefront.api_urls")),
    # ponytail: Django's own static-file view, not gated by DEBUG — fine at
    # this app's scale, swap for object storage/CDN if upload volume grows.
    path(
        f"{settings.MEDIA_URL.lstrip('/')}<path:path>",
        serve_media,
        {"document_root": settings.MEDIA_ROOT},
    ),
]
