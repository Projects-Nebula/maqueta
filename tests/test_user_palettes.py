import pytest
from django.test import Client

from apps.editor.models import UserPalette

pytestmark = pytest.mark.django_db

URL = "/api/user-palettes/"
VARIABLES = {
    "--color-primary": "#112233",
    "--color-background": "#f8fafc",
    "--color-text": "#0f172a",
    "--color-surface": "#ffffff",
}


@pytest.fixture
def web_client(user):
    client = Client()
    client.force_login(user)
    return client


def test_create_lists_and_updates_an_owner_scoped_palette(api, user):
    response = api.post(URL, {"name": "Mi marca", "variables": VARIABLES}, format="json")

    assert response.status_code == 201
    assert response.data["slug"] == "custom-mi-marca"
    assert response.data["variables"] == VARIABLES
    palette = UserPalette.objects.get(owner=user)

    listing = api.get(URL)
    assert listing.status_code == 200
    assert listing.data[0]["id"] == palette.id

    updated = api.patch(
        f"{URL}{palette.id}/",
        {"name": "Marca renovada", "variables": {**VARIABLES, "--color-primary": "#445566"}},
        format="json",
    )
    assert updated.status_code == 200
    assert updated.data["slug"] == "custom-mi-marca"
    assert updated.data["name"] == "Marca renovada"


def test_palette_slugs_are_unique_per_owner(api):
    first = api.post(URL, {"name": "Mi marca", "variables": VARIABLES}, format="json")
    second = api.post(URL, {"name": "Mi marca", "variables": VARIABLES}, format="json")

    assert first.status_code == 201
    assert second.status_code == 201
    assert second.data["slug"] == "custom-mi-marca-2"


def test_invalid_palette_values_are_rejected(api):
    response = api.post(
        URL,
        {
            "name": "Insegura",
            "variables": {**VARIABLES, "--color-primary": "url(https://evil.example/x)"},
        },
        format="json",
    )

    assert response.status_code == 400


def test_palette_api_is_owner_scoped(api, user, other_api, other_user):
    palette = UserPalette.objects.create(
        owner=user, slug="custom-private", name="Privada", variables=VARIABLES
    )

    assert other_api.get(URL).data == []
    assert other_api.get(f"{URL}{palette.id}/").status_code == 404
    assert other_api.delete(f"{URL}{palette.id}/").status_code == 404
    assert UserPalette.objects.filter(owner=user, pk=palette.id).exists()


def test_editor_injects_only_the_current_users_palettes(web_client, user, other_user):
    UserPalette.objects.create(owner=user, slug="custom-own", name="Propia", variables=VARIABLES)
    UserPalette.objects.create(
        owner=other_user, slug="custom-other", name="Ajena", variables=VARIABLES
    )

    response = web_client.get("/editor/")

    assert response.status_code == 200
    assert b"custom-own" in response.content
    assert b"custom-other" not in response.content
