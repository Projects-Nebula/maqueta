from django.urls import path

from .views import connection_view

app_name = "hotmart"

urlpatterns = [
    path("", connection_view, name="connection"),
]
