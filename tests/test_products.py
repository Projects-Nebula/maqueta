import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.editor.models import UploadedAsset
from apps.storefront.models import Product

pytestmark = pytest.mark.django_db

URL = "/api/products/"


def _pdf_bytes():
    return b"%PDF-1.4\n%fake pdf content for tests\n"


def test_create_product_minimal(api):
    response = api.post(URL, {"name": "Ebook", "price_cents": 1999}, format="json")
    assert response.status_code == 201
    assert response.data["price_cents"] == 1999
    assert response.data["has_digital_file"] is False
    assert response.data["is_active"] is True


def test_create_product_via_multipart_defaults_to_active(api):
    # Regression: DRF's BooleanField treats an absent key as False for
    # multipart/form data (HTML checkbox convention), which silently
    # created inactive products through the file-upload form until this
    # was pinned with an explicit default=True on the serializer field.
    response = api.post(URL, {"name": "Ebook", "price_cents": 1999}, format="multipart")
    assert response.status_code == 201
    assert response.data["is_active"] is True


def test_price_must_be_positive(api):
    response = api.post(URL, {"name": "Free?", "price_cents": 0}, format="json")
    assert response.status_code == 400


def test_products_are_owner_scoped(api, other_api, user):
    Product.objects.create(owner=user, name="Mine", price_cents=500)
    response = other_api.get(URL)
    assert response.status_code == 200
    assert response.data == []


def test_cannot_reference_another_users_uploaded_asset_as_image(api, other_user):
    other_asset = UploadedAsset.objects.create(owner=other_user, width=10, height=10)
    response = api.post(
        URL, {"name": "Sneaky", "price_cents": 500, "image": other_asset.id}, format="json"
    )
    assert response.status_code == 400


def test_digital_file_upload_accepted_when_valid_pdf(api):
    upload = SimpleUploadedFile("book.pdf", _pdf_bytes(), content_type="application/pdf")
    response = api.post(
        URL,
        {"name": "Ebook", "price_cents": 1999, "digital_file": upload},
        format="multipart",
    )
    assert response.status_code == 201
    assert response.data["has_digital_file"] is True


def test_digital_file_upload_rejects_non_pdf_disguised_as_pdf(api):
    upload = SimpleUploadedFile("evil.pdf", b"not a real pdf", content_type="application/pdf")
    response = api.post(
        URL,
        {"name": "Ebook", "price_cents": 1999, "digital_file": upload},
        format="multipart",
    )
    assert response.status_code == 400


def test_digital_file_upload_rejects_oversized_file(api, monkeypatch):
    monkeypatch.setattr("apps.storefront.file_validation.MAX_UPLOAD_BYTES", 10)
    upload = SimpleUploadedFile("book.pdf", _pdf_bytes(), content_type="application/pdf")
    response = api.post(
        URL,
        {"name": "Ebook", "price_cents": 1999, "digital_file": upload},
        format="multipart",
    )
    assert response.status_code == 400


def test_update_and_delete_are_owner_scoped(api, other_api, user):
    product = Product.objects.create(owner=user, name="Mine", price_cents=500)
    assert (
        other_api.patch(f"{URL}{product.id}/", {"is_active": False}, format="json").status_code
        == 404
    )
    assert other_api.delete(f"{URL}{product.id}/").status_code == 404
    assert api.patch(f"{URL}{product.id}/", {"is_active": False}, format="json").status_code == 200
