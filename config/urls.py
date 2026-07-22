"""Root URL configuration."""

from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


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
]
