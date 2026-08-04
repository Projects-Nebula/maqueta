import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.vercel.client import FakeVercelClient


@pytest.fixture(autouse=True)
def _clear_throttle_cache():
    # Throttling stores counters in the cache; isolate every test.
    cache.clear()
    yield
    cache.clear()


@pytest.fixture(autouse=True)
def _fake_vercel_client_by_default(monkeypatch):
    """build_vercel_client() picks RealVercelClient whenever VERCEL_TOKEN is
    set (see apps/vercel/client.py) - with a real token in a dev's local
    .env, every un-mocked deploy_bundle() call in the test suite hit the
    live Vercel API and created a real throwaway project that was never
    cleaned up (147 accumulated on one dev account before this fixture
    existed). Tests must be deterministic and offline regardless of local
    env config. Tests needing custom fake behavior (failures, capturing
    calls) override this with their own monkeypatch.setattr in the test
    body, which wins over this autouse one."""
    monkeypatch.setattr("apps.vercel.services.build_vercel_client", lambda: FakeVercelClient())


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
