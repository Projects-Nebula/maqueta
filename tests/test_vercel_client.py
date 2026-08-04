import httpx
import pytest

from apps.vercel.client import (
    Deployment,
    DeploymentFile,
    FakeVercelClient,
    RealVercelClient,
    VercelClientError,
    build_vercel_client,
)


def test_build_vercel_client_returns_fake_when_token_empty(settings):
    settings.VERCEL_TOKEN = ""

    client = build_vercel_client()

    assert isinstance(client, FakeVercelClient)


def test_build_vercel_client_returns_fake_when_token_none(settings):
    settings.VERCEL_TOKEN = None

    client = build_vercel_client()

    assert isinstance(client, FakeVercelClient)


def test_build_vercel_client_returns_real_when_token_set(settings):
    settings.VERCEL_TOKEN = "vercel-token"

    client = build_vercel_client()

    assert isinstance(client, RealVercelClient)


def test_fake_client_create_deployment_returns_deployment():
    client = FakeVercelClient()

    deployment = client.create_deployment(
        project_name="mq-my-bundle",
        files=[DeploymentFile(path="index.html", data=b"<html></html>")],
    )

    assert isinstance(deployment, Deployment)
    assert deployment.id
    assert deployment.project_id
    assert deployment.aliases
    assert deployment.ready_state


def test_fake_client_create_deployment_is_deterministic_alias_per_project():
    client = FakeVercelClient()

    first = client.create_deployment(
        project_name="mq-same-bundle",
        files=[DeploymentFile(path="index.html", data=b"<html></html>")],
    )
    second = client.create_deployment(
        project_name="mq-same-bundle",
        files=[DeploymentFile(path="index.html", data=b"<html>v2</html>")],
    )

    assert first.aliases == second.aliases


def test_fake_client_two_projects_never_share_an_alias():
    client = FakeVercelClient()

    first = client.create_deployment(
        project_name="mq-bundle-a",
        files=[DeploymentFile(path="index.html", data=b"a")],
    )
    second = client.create_deployment(
        project_name="mq-bundle-b",
        files=[DeploymentFile(path="index.html", data=b"b")],
    )

    assert set(first.aliases).isdisjoint(second.aliases)
    assert first.project_id != second.project_id


def test_fake_client_get_deployment_returns_deployment():
    client = FakeVercelClient()

    deployment = client.get_deployment("fake-dpl-123")

    assert deployment.id == "fake-dpl-123"


def test_fake_client_delete_project_does_not_raise():
    client = FakeVercelClient()

    client.delete_project("mq-my-bundle")


class TestRealVercelClientCreateDeployment:
    def _client(self, team_id=""):
        return RealVercelClient(
            token="vercel-token",
            api_base_url="https://api.example.com",
            timeout=5,
            team_id=team_id,
        )

    @staticmethod
    def _fake_patch_ok(captured=None):
        """New projects inherit the team's default SSO deployment
        protection - create_deployment() always PATCHes it off afterward
        (see RealVercelClient._disable_deployment_protection). A default
        success stub for tests that aren't specifically asserting on it."""

        def _fake_patch(url, *, params, json, headers, timeout):
            if captured is not None:
                captured["patch_url"] = url
                captured["patch_params"] = params
                captured["patch_json"] = json
            request = httpx.Request("PATCH", url)
            return httpx.Response(200, json={}, request=request)

        return _fake_patch

    def test_create_deployment_posts_expected_shape(self, monkeypatch):
        """Matches the verified live Vercel response shape: POST
        /v13/deployments auto-creates the named project — no separate
        /v9/projects call — and the response carries id, url, alias,
        readyState, projectId."""
        captured = {}

        def _fake_post(url, *, params, json, headers, timeout):
            captured["url"] = url
            captured["params"] = params
            captured["json"] = json
            captured["headers"] = headers
            request = httpx.Request("POST", url)
            return httpx.Response(
                200,
                json={
                    "id": "dpl_123",
                    "url": "mq-my-bundle-abc123.vercel.app",
                    "alias": ["mq-my-bundle-account.vercel.app"],
                    "readyState": "INITIALIZING",
                    "projectId": "prj_abc",
                },
                request=request,
            )

        monkeypatch.setattr("httpx.post", _fake_post)
        monkeypatch.setattr("httpx.patch", self._fake_patch_ok(captured))

        deployment = self._client().create_deployment(
            project_name="mq-my-bundle",
            files=[DeploymentFile(path="index.html", data=b"<html></html>")],
        )

        assert captured["url"] == "https://api.example.com/v13/deployments"
        assert captured["json"]["name"] == "mq-my-bundle"
        assert captured["json"]["target"] == "production"
        assert captured["json"]["projectSettings"] == {"framework": None}
        assert captured["json"]["files"][0]["file"] == "index.html"
        assert captured["json"]["files"][0]["encoding"] == "base64"
        assert captured["headers"]["Authorization"] == "Bearer vercel-token"
        assert captured["params"] == {}
        assert deployment.id == "dpl_123"
        assert deployment.project_id == "prj_abc"
        assert deployment.aliases == ["mq-my-bundle-account.vercel.app"]
        assert deployment.ready_state == "INITIALIZING"

    def test_create_deployment_disables_deployment_protection(self, monkeypatch):
        """Regression test: verified live against a real Vercel team that a
        freshly-created project comes back with ssoProtection set to
        {"deploymentType": "all_except_custom_domains"} - since every
        bundle this app deploys lands on the default *.vercel.app domain
        (never a custom one), every seller's page 302-redirected anonymous
        buyers to a Vercel SSO login instead of showing the page, until
        explicitly cleared via PATCH /v9/projects/{name}."""

        def _fake_post(url, *, params, json, headers, timeout):
            request = httpx.Request("POST", url)
            return httpx.Response(
                200,
                json={
                    "id": "dpl_123",
                    "url": "mq-my-bundle-abc123.vercel.app",
                    "alias": ["mq-my-bundle-account.vercel.app"],
                    "readyState": "INITIALIZING",
                    "projectId": "prj_abc",
                },
                request=request,
            )

        captured = {}
        monkeypatch.setattr("httpx.post", _fake_post)
        monkeypatch.setattr("httpx.patch", self._fake_patch_ok(captured))

        self._client(team_id="team_123").create_deployment(
            project_name="mq-my-bundle",
            files=[DeploymentFile(path="index.html", data=b"<html></html>")],
        )

        assert captured["patch_url"] == "https://api.example.com/v9/projects/mq-my-bundle"
        assert captured["patch_params"] == {"teamId": "team_123"}
        assert captured["patch_json"] == {"ssoProtection": None}

    def test_create_deployment_raises_if_disabling_protection_fails(self, monkeypatch):
        def _fake_post(url, *, params, json, headers, timeout):
            request = httpx.Request("POST", url)
            return httpx.Response(
                200,
                json={
                    "id": "dpl_123",
                    "url": "x.vercel.app",
                    "alias": ["x.vercel.app"],
                    "readyState": "INITIALIZING",
                    "projectId": "prj_abc",
                },
                request=request,
            )

        def _fake_patch(url, *, params, json, headers, timeout):
            request = httpx.Request("PATCH", url)
            response = httpx.Response(500, json={"error": "boom"}, request=request)
            raise httpx.HTTPStatusError("boom", request=request, response=response)

        monkeypatch.setattr("httpx.post", _fake_post)
        monkeypatch.setattr("httpx.patch", _fake_patch)

        with pytest.raises(VercelClientError):
            self._client().create_deployment(
                project_name="mq-my-bundle",
                files=[DeploymentFile(path="index.html", data=b"x")],
            )

    def test_create_deployment_sends_team_id_only_when_configured(self, monkeypatch):
        captured = {}

        def _fake_post(url, *, params, json, headers, timeout):
            captured["params"] = params
            request = httpx.Request("POST", url)
            return httpx.Response(
                200,
                json={
                    "id": "dpl_1",
                    "url": "x.vercel.app",
                    "alias": ["x.vercel.app"],
                    "readyState": "INITIALIZING",
                    "projectId": "prj_1",
                },
                request=request,
            )

        monkeypatch.setattr("httpx.post", _fake_post)
        monkeypatch.setattr("httpx.patch", self._fake_patch_ok())

        self._client(team_id="team_123").create_deployment(
            project_name="mq-my-bundle",
            files=[DeploymentFile(path="index.html", data=b"x")],
        )

        assert captured["params"] == {"teamId": "team_123"}

    def test_create_deployment_raises_vercel_client_error_on_http_error(self, monkeypatch):
        def _fake_post(url, *, params, json, headers, timeout):
            request = httpx.Request("POST", url)
            response = httpx.Response(401, json={"error": "forbidden"}, request=request)
            raise httpx.HTTPStatusError("forbidden", request=request, response=response)

        monkeypatch.setattr("httpx.post", _fake_post)

        with pytest.raises(VercelClientError):
            self._client().create_deployment(
                project_name="mq-my-bundle",
                files=[DeploymentFile(path="index.html", data=b"x")],
            )

    def test_create_deployment_raises_on_timeout(self, monkeypatch):
        def _fake_post(url, *, params, json, headers, timeout):
            raise httpx.TimeoutException("timed out")

        monkeypatch.setattr("httpx.post", _fake_post)

        with pytest.raises(VercelClientError):
            self._client().create_deployment(
                project_name="mq-my-bundle",
                files=[DeploymentFile(path="index.html", data=b"x")],
            )

    def test_create_deployment_raises_on_unexpected_payload_shape(self, monkeypatch):
        def _fake_post(url, *, params, json, headers, timeout):
            request = httpx.Request("POST", url)
            return httpx.Response(200, json={"unexpected": "shape"}, request=request)

        monkeypatch.setattr("httpx.post", _fake_post)

        with pytest.raises(VercelClientError):
            self._client().create_deployment(
                project_name="mq-my-bundle",
                files=[DeploymentFile(path="index.html", data=b"x")],
            )


class TestRealVercelClientGetDeployment:
    def _client(self):
        return RealVercelClient(
            token="vercel-token",
            api_base_url="https://api.example.com",
            timeout=5,
        )

    def test_get_deployment_requests_the_deployment_endpoint(self, monkeypatch):
        captured = {}

        def _fake_get(url, *, params, headers, timeout):
            captured["url"] = url
            request = httpx.Request("GET", url)
            return httpx.Response(
                200,
                json={
                    "id": "dpl_123",
                    "url": "mq-my-bundle-abc123.vercel.app",
                    "alias": ["mq-my-bundle-account.vercel.app"],
                    "readyState": "READY",
                    "projectId": "prj_abc",
                },
                request=request,
            )

        monkeypatch.setattr("httpx.get", _fake_get)

        deployment = self._client().get_deployment("dpl_123")

        assert captured["url"] == "https://api.example.com/v13/deployments/dpl_123"
        assert deployment.ready_state == "READY"

    def test_get_deployment_tolerates_missing_alias(self, monkeypatch):
        def _fake_get(url, *, params, headers, timeout):
            request = httpx.Request("GET", url)
            return httpx.Response(
                200,
                json={
                    "id": "dpl_123",
                    "url": "mq-my-bundle-abc123.vercel.app",
                    "readyState": "READY",
                    "projectId": "prj_abc",
                },
                request=request,
            )

        monkeypatch.setattr("httpx.get", _fake_get)

        deployment = self._client().get_deployment("dpl_123")

        assert deployment.aliases == []

    def test_get_deployment_raises_vercel_client_error_on_http_error(self, monkeypatch):
        def _fake_get(url, *, params, headers, timeout):
            request = httpx.Request("GET", url)
            response = httpx.Response(404, json={"error": "not_found"}, request=request)
            raise httpx.HTTPStatusError("not found", request=request, response=response)

        monkeypatch.setattr("httpx.get", _fake_get)

        with pytest.raises(VercelClientError):
            self._client().get_deployment("dpl_123")


class TestRealVercelClientDeleteProject:
    def _client(self):
        return RealVercelClient(
            token="vercel-token",
            api_base_url="https://api.example.com",
            timeout=5,
        )

    def test_delete_project_calls_expected_endpoint(self, monkeypatch):
        captured = {}

        def _fake_delete(url, *, params, headers, timeout):
            captured["url"] = url
            captured["headers"] = headers
            request = httpx.Request("DELETE", url)
            return httpx.Response(204, request=request)

        monkeypatch.setattr("httpx.delete", _fake_delete)

        self._client().delete_project("mq-my-bundle")

        assert captured["url"] == "https://api.example.com/v9/projects/mq-my-bundle"
        assert captured["headers"]["Authorization"] == "Bearer vercel-token"

    def test_delete_project_raises_vercel_client_error_on_http_error(self, monkeypatch):
        def _fake_delete(url, *, params, headers, timeout):
            request = httpx.Request("DELETE", url)
            response = httpx.Response(404, json={"error": "not_found"}, request=request)
            raise httpx.HTTPStatusError("not found", request=request, response=response)

        monkeypatch.setattr("httpx.delete", _fake_delete)

        with pytest.raises(VercelClientError):
            self._client().delete_project("mq-my-bundle")
