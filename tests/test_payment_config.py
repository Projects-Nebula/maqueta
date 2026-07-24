import pytest

from apps.storefront.models import PaymentGatewayConfig

pytestmark = pytest.mark.django_db

URL = "/api/payment-gateway-configs/"


def _config(owner, credentials=None):
    config = PaymentGatewayConfig.objects.create(owner=owner, gateway="stripe", is_enabled=True)
    if credentials is not None:
        config.set_credentials(credentials)
        config.save(update_fields=["credentials_encrypted"])
    return config


def test_validate_checks_stored_credentials_without_creating_checkout(api, user):
    config = _config(user, {"secret_key": "sk_test_example"})

    response = api.post(f"{URL}{config.id}/validate/")

    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_validate_reports_missing_required_credentials(api, user):
    config = _config(user)

    response = api.post(f"{URL}{config.id}/validate/")

    assert response.status_code == 400
    assert response.json() == {
        "ok": False,
        "error": "missing_credentials",
        "missing": ["secret_key"],
    }


def test_validate_is_owner_scoped(api, other_user, user):
    config = _config(other_user, {"secret_key": "sk_test_example"})

    response = api.post(f"{URL}{config.id}/validate/")

    assert response.status_code == 404
