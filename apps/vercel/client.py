"""Vercel deployment client — mirrors apps/hotmart/client.py's shape:

ABC + Real (httpx) + Fake (offline stub) + build_vercel_client() factory,
with base URLs/timeout in settings so endpoint drift is a config fix, not a
code change. Unlike Hotmart, the Vercel credential is platform-level (a
single `VERCEL_TOKEN`), not per-seller — see design.md's confirmed decision.

Verified against the real Vercel API with a real token (2026-08-02, live
call — see design.md ADR "One Vercel project per SiteBundle" and tasks.md
1.1). This REPLACES the design doc's original assumption of a separate
`POST /v9/projects` prerequisite call:

- `POST {base}/v13/deployments` with JSON body `{"name": <project-name>,
  "files": [{"file": <path>, "data": <content>}], "target": "production",
  "projectSettings": {"framework": null}}` and header
  `Authorization: Bearer <token>` returns 200 and AUTO-CREATES the named
  project if it doesn't already exist. No separate project-creation call is
  needed as a prerequisite — the design's planned `ensure_project()` method
  was dropped entirely; `create_deployment()` alone gets-or-creates the
  project and deploys to it.
- Response JSON has: `id` (`dpl_...`), `url` (per-deployment hostname,
  includes a random hash, CHANGES every deployment — never surfaced as "the
  site's URL"), `alias` (list of STABLE hostnames like
  `{project-name}-{team-or-username-slug}.vercel.app` that persist across
  redeploys to the same project — THIS is what callers must treat as the
  site's public URL), `readyState` (starts `"INITIALIZING"`; polling to
  `"READY"` was not verified live and is out of scope for this client —
  callers needing readiness must poll `get_deployment()` themselves),
  `projectId`.
- `DELETE {base}/v9/projects/{name}` deletes a project, returns 204.
- No call needs an explicit `teamId` for a personal-account token — verified
  across deployments, project list, user info, and project delete. Team
  tokens may still need it, so `VERCEL_TEAM_ID` stays optional and is only
  sent as a query param when explicitly configured.

Not live-verified in this pass: the exact `GET /v13/deployments/{id}`
response shape (assumed to match the creation response) and whether binary
(non-text) file content must be base64-encoded — the live test only sent
one text file (`index.html`) as raw string data with no `encoding` field.
This client base64-encodes every file's bytes with an explicit
`"encoding": "base64"`, which is documented Vercel API behavior and is
required once binary assets are deployed (PR2); it gives one code path for
both text and binary instead of branching on content type.
"""

from __future__ import annotations

import base64
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx
from django.conf import settings


class VercelClientError(Exception):
    """Raised for any non-2xx response, timeout, or unexpected payload
    shape from Vercel. Callers never see raw upstream JSON."""


@dataclass(frozen=True)
class DeploymentFile:
    path: str  # POSIX-relative in-bundle path, e.g. "assets/logo.png"
    data: bytes


@dataclass(frozen=True)
class Deployment:
    id: str
    project_id: str
    url: str  # per-deployment hostname — unstable, changes every deploy
    aliases: list[str]  # stable production hostname(s) — the public URL
    ready_state: str


class VercelClient(ABC):
    @abstractmethod
    def create_deployment(self, *, project_name: str, files: list[DeploymentFile]) -> Deployment:
        """Create (or update, on redeploy) a production deployment for
        `project_name`. Auto-creates the Vercel project if it doesn't exist
        yet — no separate project-creation call is required."""
        ...

    @abstractmethod
    def get_deployment(self, deployment_id: str) -> Deployment: ...

    @abstractmethod
    def delete_project(self, project_name: str) -> None:
        """Delete a Vercel project and all its deployments. Used by the
        manual-takedown flow (PR5)."""
        ...


class RealVercelClient(VercelClient):
    """Talks to the real Vercel API via httpx. Base URL/timeout come from
    settings (not hardcoded) so documented-vs-actual endpoint drift is a
    config fix. Every request carries an explicit timeout."""

    def __init__(
        self,
        *,
        token: str,
        api_base_url: str,
        timeout: float,
        team_id: str = "",
    ) -> None:
        self._token = token
        self._api_base_url = api_base_url.rstrip("/")
        self._timeout = timeout
        self._team_id = team_id

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._token}"}

    def _team_params(self) -> dict:
        return {"teamId": self._team_id} if self._team_id else {}

    def create_deployment(self, *, project_name: str, files: list[DeploymentFile]) -> Deployment:
        payload = {
            "name": project_name,
            "target": "production",
            "projectSettings": {"framework": None},
            "files": [
                {
                    "file": file.path,
                    "data": base64.b64encode(file.data).decode("ascii"),
                    "encoding": "base64",
                }
                for file in files
            ],
        }
        try:
            response = httpx.post(
                f"{self._api_base_url}/v13/deployments",
                params=self._team_params(),
                json=payload,
                headers=self._headers(),
                timeout=self._timeout,
            )
            response.raise_for_status()
            return self._deployment_from_payload(response.json())
        except httpx.HTTPError as exc:
            raise VercelClientError(f"vercel deployment creation failed: {exc}") from exc
        except (KeyError, ValueError, TypeError) as exc:
            raise VercelClientError("vercel deployment response had an unexpected shape") from exc

    def get_deployment(self, deployment_id: str) -> Deployment:
        try:
            response = httpx.get(
                f"{self._api_base_url}/v13/deployments/{deployment_id}",
                params=self._team_params(),
                headers=self._headers(),
                timeout=self._timeout,
            )
            response.raise_for_status()
            return self._deployment_from_payload(response.json())
        except httpx.HTTPError as exc:
            raise VercelClientError(f"vercel deployment lookup failed: {exc}") from exc
        except (KeyError, ValueError, TypeError) as exc:
            raise VercelClientError("vercel deployment response had an unexpected shape") from exc

    def delete_project(self, project_name: str) -> None:
        try:
            response = httpx.delete(
                f"{self._api_base_url}/v9/projects/{project_name}",
                params=self._team_params(),
                headers=self._headers(),
                timeout=self._timeout,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise VercelClientError(f"vercel project deletion failed: {exc}") from exc

    @staticmethod
    def _deployment_from_payload(body: dict) -> Deployment:
        return Deployment(
            id=str(body["id"]),
            project_id=str(body["projectId"]),
            url=str(body["url"]),
            aliases=list(body.get("alias") or []),
            ready_state=str(body.get("readyState", "")),
        )


class FakeVercelClient(VercelClient):
    """Offline stand-in used whenever VERCEL_TOKEN is absent — same role as
    apps.hotmart.client.FakeHotmartClient. Lets the entire test suite (and
    local dev) run green with zero Vercel credentials. Aliases are
    deterministic per project name so two calls for the same project (a
    redeploy) return the same stable URL, and two different projects never
    collide."""

    def create_deployment(self, *, project_name: str, files: list[DeploymentFile]) -> Deployment:
        return Deployment(
            id=f"fake-dpl-{uuid.uuid4().hex[:12]}",
            project_id=f"fake-prj-{project_name}",
            url=f"fake-{project_name}-{uuid.uuid4().hex[:8]}.vercel.app",
            aliases=[f"{project_name}.vercel.app"],
            ready_state="READY",
        )

    def get_deployment(self, deployment_id: str) -> Deployment:
        return Deployment(
            id=deployment_id,
            project_id="fake-project",
            url="fake-deployment.vercel.app",
            aliases=["fake-deployment.vercel.app"],
            ready_state="READY",
        )

    def delete_project(self, project_name: str) -> None:
        return None


def build_vercel_client() -> VercelClient:
    """settings.VERCEL_TOKEN set (non-empty) -> RealVercelClient, otherwise
    FakeVercelClient. Platform-level, not per-seller — same "no partial
    config" doctrine as build_hotmart_client(), simplified because there is
    only one credential to check instead of a client_id/client_secret pair."""
    token = settings.VERCEL_TOKEN or ""
    if token:
        return RealVercelClient(
            token=token,
            api_base_url=settings.VERCEL_API_BASE_URL,
            timeout=settings.VERCEL_REQUEST_TIMEOUT,
            team_id=settings.VERCEL_TEAM_ID or "",
        )
    return FakeVercelClient()
