from django.contrib import admin

from .models import Template, UserPalette, UserTemplate, UserTemplateRevision


@admin.register(Template)
class TemplateAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "order", "updated_at"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ["name"]}


@admin.register(UserTemplate)
class UserTemplateAdmin(admin.ModelAdmin):
    list_display = ["name", "owner", "updated_at"]
    search_fields = ["name", "owner__username"]


@admin.register(UserPalette)
class UserPaletteAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "owner", "updated_at"]
    search_fields = ["name", "slug", "owner__username"]


@admin.register(UserTemplateRevision)
class UserTemplateRevisionAdmin(admin.ModelAdmin):
    list_display = ["user_template", "version", "created_at"]
