from apps.hotmart.client import FakeHotmartClient, RealHotmartClient, build_hotmart_client


def test_build_hotmart_client_returns_fake_when_no_credentials(settings):
    settings.HOTMART_CLIENT_ID = ""
    settings.HOTMART_CLIENT_SECRET = ""

    client = build_hotmart_client()

    assert isinstance(client, FakeHotmartClient)


def test_build_hotmart_client_returns_fake_when_only_client_id_set(settings):
    settings.HOTMART_CLIENT_ID = "client-id"
    settings.HOTMART_CLIENT_SECRET = ""

    client = build_hotmart_client()

    assert isinstance(client, FakeHotmartClient)


def test_build_hotmart_client_returns_fake_when_only_client_secret_set(settings):
    settings.HOTMART_CLIENT_ID = ""
    settings.HOTMART_CLIENT_SECRET = "client-secret"

    client = build_hotmart_client()

    assert isinstance(client, FakeHotmartClient)


def test_build_hotmart_client_returns_real_when_credentials_complete(settings):
    settings.HOTMART_CLIENT_ID = "client-id"
    settings.HOTMART_CLIENT_SECRET = "client-secret"

    client = build_hotmart_client()

    assert isinstance(client, RealHotmartClient)


def test_fake_client_exchange_code_returns_token_bundle():
    client = FakeHotmartClient()

    bundle = client.exchange_code("some-code")

    assert bundle.access_token
    assert bundle.refresh_token
    assert bundle.expires_in > 0


def test_fake_client_refresh_returns_token_bundle():
    client = FakeHotmartClient()

    bundle = client.refresh("some-refresh-token")

    assert bundle.access_token
    assert bundle.refresh_token
    assert bundle.expires_in > 0


def test_fake_client_list_products_returns_products():
    client = FakeHotmartClient()

    products = client.list_products("some-access-token")

    assert isinstance(products, list)
