from django.urls import path

from .views import analytics_dashboard_view

app_name = "analytics"

urlpatterns = [
    path("", analytics_dashboard_view, name="dashboard"),
]
