from django.contrib import admin

from .models import Project, ProjectRevision

admin.site.register(Project)
admin.site.register(ProjectRevision)
