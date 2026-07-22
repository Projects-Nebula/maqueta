import pytest

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
