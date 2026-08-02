from django.urls import path

from .views import DisconnectView

app_name = "hotmart_api"

urlpatterns = [
    path("disconnect/", DisconnectView.as_view(), name="disconnect"),
]
