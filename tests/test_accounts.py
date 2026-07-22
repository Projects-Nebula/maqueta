import pytest
from django.contrib.auth import get_user_model
from django.test import Client

pytestmark = pytest.mark.django_db

SIGNUP_URL = "/signup/"


def test_signup_page_loads():
    response = Client().get(SIGNUP_URL)
    assert response.status_code == 200


def test_signup_creates_user_and_logs_in():
    client = Client()
    response = client.post(
        SIGNUP_URL,
        {
            "username": "newuser",
            "password1": "a-very-safe-pw-123",
            "password2": "a-very-safe-pw-123",
        },
    )
    assert response.status_code == 302
    assert get_user_model().objects.filter(username="newuser").exists()
    # Logged in immediately: the next request carries an authenticated session.
    home = client.get("/editor/")
    assert home.status_code == 200


def test_signup_rejects_mismatched_passwords():
    client = Client()
    response = client.post(
        SIGNUP_URL,
        {
            "username": "newuser2",
            "password1": "a-very-safe-pw-123",
            "password2": "different-pw-456",
        },
    )
    assert response.status_code == 200
    assert not get_user_model().objects.filter(username="newuser2").exists()


def test_signup_rejects_weak_password():
    client = Client()
    response = client.post(
        SIGNUP_URL,
        {"username": "newuser3", "password1": "password", "password2": "password"},
    )
    assert response.status_code == 200
    assert not get_user_model().objects.filter(username="newuser3").exists()


def test_signup_rejects_duplicate_username(user):
    client = Client()
    response = client.post(
        SIGNUP_URL,
        {
            "username": user.username,
            "password1": "a-very-safe-pw-123",
            "password2": "a-very-safe-pw-123",
        },
    )
    assert response.status_code == 200
    assert get_user_model().objects.filter(username=user.username).count() == 1


def test_authenticated_user_visiting_signup_is_redirected(user):
    client = Client()
    client.force_login(user)
    response = client.get(SIGNUP_URL)
    assert response.status_code == 302
