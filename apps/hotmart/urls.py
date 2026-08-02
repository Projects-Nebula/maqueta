from django.urls import path

from .views import callback_view, connect_view, connection_view

app_name = "hotmart"

urlpatterns = [
    path("", connection_view, name="connection"),
    path("conectar/", connect_view, name="connect"),
    path("callback/", callback_view, name="callback"),
]
