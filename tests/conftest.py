import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APIClient


@pytest.fixture(autouse=True)
def _clear_throttle_cache():
    # Throttling stores counters in the cache; isolate every test.
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def user(db):
    return get_user_model().objects.create_user("alice", password="pw-alice-123")


@pytest.fixture
def other_user(db):
    return get_user_model().objects.create_user("bob", password="pw-bob-123")


@pytest.fixture
def api(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.fixture
def other_api(other_user):
    client = APIClient()
    client.force_authenticate(other_user)
    return client


@pytest.fixture
def anon_api():
    return APIClient()
