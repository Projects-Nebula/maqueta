import pytest
from django.utils import timezone

from apps.hotmart.models import HotmartConnection

pytestmark = pytest.mark.django_db


def test_set_tokens_encrypts_at_rest(user):
    connection = HotmartConnection.objects.create(owner=user)

    connection.set_tokens(
        access="access-token-value", refresh="refresh-token-value", expires_in=3600
    )

    assert connection.access_token_encrypted != "access-token-value"
    assert connection.refresh_token_encrypted != "refresh-token-value"
    assert "access-token-value" not in connection.access_token_encrypted
    assert "refresh-token-value" not in connection.refresh_token_encrypted


def test_get_access_token_round_trip(user):
    connection = HotmartConnection.objects.create(owner=user)
    connection.set_tokens(
        access="access-token-value", refresh="refresh-token-value", expires_in=3600
    )

    assert connection.get_access_token() == "access-token-value"


def test_get_access_token_returns_empty_string_on_rotated_key(user, settings):
    connection = HotmartConnection.objects.create(owner=user)
    connection.set_tokens(
        access="access-token-value", refresh="refresh-token-value", expires_in=3600
    )

    settings.SECRET_KEY = "a-completely-different-secret-key"

    assert connection.get_access_token() == ""


def test_is_expired_true_when_past_expiry(user):
    connection = HotmartConnection.objects.create(owner=user)
    connection.set_tokens(access="a", refresh="r", expires_in=-3600)

    assert connection.is_expired is True


def test_is_expired_false_when_well_within_expiry(user):
    connection = HotmartConnection.objects.create(owner=user)
    connection.set_tokens(access="a", refresh="r", expires_in=3600)

    assert connection.is_expired is False


def test_is_expired_true_within_skew_window(user):
    connection = HotmartConnection.objects.create(owner=user)
    connection.set_tokens(access="a", refresh="r", expires_in=30)

    assert connection.is_expired is True


def test_is_expired_true_when_no_expiry_set(user):
    connection = HotmartConnection.objects.create(owner=user)

    assert connection.is_expired is True


def test_set_tokens_stores_expires_at(user):
    connection = HotmartConnection.objects.create(owner=user)
    before = timezone.now()

    connection.set_tokens(access="a", refresh="r", expires_in=3600)

    assert connection.expires_at > before
