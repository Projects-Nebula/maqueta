import pytest

from apps.projects.views import REVISION_RETENTION_LIMIT

pytestmark = pytest.mark.django_db

URL = "/api/projects/"


def _create(api, name="Landing"):
    response = api.post(URL, {"name": name, "state": {"a": 1}}, format="json")
    assert response.status_code == 201
    return response.json()["id"]


def test_user_creates_project(api):
    project_id = _create(api)
    assert project_id


def test_other_user_cannot_read_project(api, other_api):
    project_id = _create(api)
    response = other_api.get(f"{URL}{project_id}/")
    assert response.status_code == 404


def test_other_user_cannot_modify_project(api, other_api):
    project_id = _create(api)
    response = other_api.patch(f"{URL}{project_id}/", {"name": "hacked"}, format="json")
    assert response.status_code == 404


def test_create_and_list_revisions(api):
    project_id = _create(api)
    created = api.post(
        f"{URL}{project_id}/revisions/",
        {"state": {"v": 1}, "source": "ai", "summary": "cambio de IA"},
        format="json",
    )
    assert created.status_code == 201
    body = created.json()
    assert body["version"] == 1
    assert body["source"] == "ai"

    listed = api.get(f"{URL}{project_id}/revisions/")
    assert listed.status_code == 200
    assert len(listed.json()) == 1


def test_revision_history_is_capped_at_retention_limit(api):
    project_id = _create(api)
    for i in range(REVISION_RETENTION_LIMIT + 6):
        response = api.post(f"{URL}{project_id}/revisions/", {"state": {"v": i}}, format="json")
        assert response.status_code == 201

    listed = api.get(f"{URL}{project_id}/revisions/")
    assert listed.status_code == 200
    assert len(listed.json()) == REVISION_RETENTION_LIMIT
    versions = sorted(r["version"] for r in listed.json())
    assert versions[0] == 7
    assert versions[-1] == REVISION_RETENTION_LIMIT + 6
