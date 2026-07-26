import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.editor.models import UploadedAsset
from apps.editor.views import MAX_UPLOADED_ASSETS_PER_USER

pytestmark = pytest.mark.django_db

URL = "/api/user-templates/wizard-images/"


def _png_bytes(width=100, height=100, color="red"):
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color=color).save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture(autouse=True)
def _media_root(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


def test_requires_authentication(anon_api):
    upload = SimpleUploadedFile("x.png", _png_bytes(), content_type="image/png")
    response = anon_api.post(URL, {"file": upload}, format="multipart")
    assert response.status_code in (401, 403)


def test_valid_upload_is_resized_and_reencoded(api):
    upload = SimpleUploadedFile("x.png", _png_bytes(200, 150), content_type="image/png")
    response = api.post(URL, {"file": upload}, format="multipart")
    assert response.status_code == 201
    body = response.json()
    assert body["width"] == 200
    assert body["height"] == 150
    assert body["url"].startswith("/media/wizard-uploads/")
    assert body["url"].endswith(".jpg")  # always re-encoded to JPEG


def test_upload_response_includes_placeholder_color(api):
    upload = SimpleUploadedFile("x.png", _png_bytes(color="red"), content_type="image/png")
    response = api.post(URL, {"file": upload}, format="multipart")
    assert response.status_code == 201
    assert response.json()["placeholder_color"] == "#ff0000"


def test_oversized_dimensions_are_downscaled(api):
    upload = SimpleUploadedFile("x.png", _png_bytes(3000, 1000), content_type="image/png")
    response = api.post(URL, {"file": upload}, format="multipart")
    assert response.status_code == 201
    body = response.json()
    assert max(body["width"], body["height"]) == 1600


def test_non_image_bytes_rejected(api):
    upload = SimpleUploadedFile("x.png", b"not an image", content_type="image/png")
    response = api.post(URL, {"file": upload}, format="multipart")
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_image"


def test_oversized_upload_rejected(api, monkeypatch):
    monkeypatch.setattr("apps.editor.image_processing.MAX_UPLOAD_BYTES", 100)
    upload = SimpleUploadedFile("x.png", _png_bytes(50, 50), content_type="image/png")
    response = api.post(URL, {"file": upload}, format="multipart")
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_image"


def test_no_file_provided_rejected(api):
    response = api.post(URL, {}, format="multipart")
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_input"


def test_per_user_asset_cap_enforced(api, user):
    UploadedAsset.objects.bulk_create(
        [
            UploadedAsset(owner=user, width=10, height=10)
            for _ in range(MAX_UPLOADED_ASSETS_PER_USER)
        ]
    )
    upload = SimpleUploadedFile("x.png", _png_bytes(), content_type="image/png")
    response = api.post(URL, {"file": upload}, format="multipart")
    assert response.status_code == 400
    assert response.json()["error"] == "too_many_assets"


def test_upload_is_owner_scoped(api, user):
    upload = SimpleUploadedFile("x.png", _png_bytes(), content_type="image/png")
    response = api.post(URL, {"file": upload}, format="multipart")
    assert response.status_code == 201
    assert UploadedAsset.objects.get().owner == user


def test_asset_can_be_deleted_by_owner(api, user, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    upload = SimpleUploadedFile("x.png", _png_bytes(), content_type="image/png")
    response = api.post(URL, {"file": upload}, format="multipart")
    asset_id = response.json()["id"]

    response = api.delete(f"{URL}{asset_id}/")

    assert response.status_code == 204
    assert not UploadedAsset.objects.filter(pk=asset_id).exists()


def test_asset_delete_is_owner_scoped(api, other_user):
    asset = UploadedAsset.objects.create(owner=other_user, width=10, height=10)

    response = api.delete(f"{URL}{asset.id}/")

    assert response.status_code == 404
    assert UploadedAsset.objects.filter(pk=asset.id).exists()
