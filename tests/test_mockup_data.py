import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import override_settings

from apps.analytics.models import AnalyticsEvent, AnalyticsSession
from apps.editor.models import Template, UserPalette, UserTemplate
from apps.projects.models import Project, ProjectRevision

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _media_root(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


@override_settings(DEBUG=True)
def test_mockup_command_resets_and_populates_the_local_catalog():
    User = get_user_model()
    User.objects.create_user(username="stale", password="stale-password")

    call_command("mockup_data", verbosity=0)

    assert not User.objects.filter(username="stale").exists()
    assert User.objects.filter(username="demo", is_superuser=True).count() == 1
    assert Template.objects.filter(slug__in=["landing", "blank", "coming-soon"]).count() == 3
    assert UserTemplate.objects.filter(owner__username="demo", is_published=True).exists()
    assert User.objects.count() == 1
    assert Project.objects.filter(owner__username="demo").count() == 1
    assert ProjectRevision.objects.filter(project__owner__username="demo").count() == 2
    assert UserPalette.objects.filter(owner__username="demo").count() == 3
    assert AnalyticsSession.objects.count() == 3
    assert AnalyticsEvent.objects.count() == 12
