from django.urls import path

from .views import editor_view, gallery_view, home_view, template_wizard_view

app_name = "editor"

urlpatterns = [
    path("editor/", editor_view, name="editor"),
    path("gallery/", gallery_view, name="gallery"),
    path("home/", home_view, name="home"),
    path("wizard/", template_wizard_view, name="template-wizard"),
]
