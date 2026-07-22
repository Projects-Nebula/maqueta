import pytest
from django.test import Client

from apps.projects.models import Project

pytestmark = pytest.mark.django_db

URL = "/editor/"


@pytest.fixture
def web_client(user):
    client = Client()
    client.force_login(user)
    return client


def test_loads_project_state_with_no_revisions_yet(web_client, user):
    project = Project.objects.create(owner=user, name="P", state={"marker": "base"})
    response = web_client.get(URL, {"p": str(project.id)})
    assert response.status_code == 200
    assert b'"marker": "base"' in response.content


def test_loads_latest_revision_state_when_present(web_client, user):
    project = Project.objects.create(owner=user, name="P", state={"marker": "base"})
    project.revisions.create(version=1, state={"marker": "v1"})
    project.revisions.create(version=2, state={"marker": "v2"})
    response = web_client.get(URL, {"p": str(project.id)})
    assert response.status_code == 200
    assert b'"marker": "v2"' in response.content
    assert b'"marker": "v1"' not in response.content


def test_other_users_project_is_not_leaked(web_client, user, other_user):
    project = Project.objects.create(owner=other_user, name="P", state={"marker": "secret"})
    response = web_client.get(URL, {"p": str(project.id)})
    assert response.status_code == 200
    assert b"secret" not in response.content


def test_malformed_project_id_does_not_500(web_client):
    response = web_client.get(URL, {"p": "not-a-uuid"})
    assert response.status_code == 200
