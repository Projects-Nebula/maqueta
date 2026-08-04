"""Deploy a validated `SiteBundle` to its own isolated Vercel project.

See design.md's "One Vercel project per SiteBundle" decision: the project
name is deterministic (`mq-{public_slug}`), so calling `create_deployment`
again for the same bundle naturally redeploys into the same project — no
separate "does a project already exist" check is needed.
"""

from __future__ import annotations

import secrets

from django.utils.text import slugify

from apps.editor.models import SiteBundle

from .client import DeploymentFile, VercelClientError, build_vercel_client
from .models import VercelDeployment

__all__ = [
    "VercelClientError",
    "deploy_bundle",
    "project_name_for_bundle",
    "unpublish_bundle",
]


def _ensure_public_slug(bundle: SiteBundle) -> str:
    """Stable once set, same pattern as `UserTemplate.publish()`: a random
    suffix avoids collisions between bundles with the same display name.
    Set lazily on first deploy — ingestion (PR2) does not need a Vercel
    identity yet, only the deploy flow does."""
    if not bundle.public_slug:
        base = slugify(bundle.name)[:100] or "bundle"
        bundle.public_slug = f"{base}-{secrets.token_hex(3)}"
        bundle.save(update_fields=["public_slug", "updated_at"])
    return bundle.public_slug


def project_name_for_bundle(bundle: SiteBundle) -> str:
    return f"mq-{_ensure_public_slug(bundle)}"


def deploy_bundle(bundle: SiteBundle) -> VercelDeployment:
    """Deploy `bundle`'s current assets and persist a `VercelDeployment` row.

    Raises `VercelClientError` on any Vercel-side failure (timeout, non-2xx,
    malformed payload) — the caller (the `deploy` view action) maps that to
    a 502. On failure NO `VercelDeployment` row is created: the row is only
    ever written after `create_deployment` has already returned
    successfully, so there is never a partially-written deployment record.
    """
    project_name = project_name_for_bundle(bundle)
    files = [
        DeploymentFile(path=asset.path, data=asset.file.read()) for asset in bundle.assets.all()
    ]

    client = build_vercel_client()
    deployment = client.create_deployment(project_name=project_name, files=files)

    return VercelDeployment.objects.create(
        bundle=bundle,
        project_id=deployment.project_id,
        deployment_id=deployment.id,
        # Aliases carry the stable production hostname; `url` is the
        # unstable per-deployment host (see client.py's Deployment
        # docstring). Fall back to `url` only if Vercel ever omits alias.
        url=f"https://{deployment.aliases[0] if deployment.aliases else deployment.url}",
        state=deployment.ready_state,
    )


def unpublish_bundle(bundle: SiteBundle) -> None:
    """Manual takedown (design: "takedown = manual admin-only unpublish").

    Deletes the bundle's entire Vercel project (all its deployments — a
    redeploy always reuses the same project, see `deploy_bundle`'s
    docstring) and only then flips `is_active` off, mirroring
    `deploy_bundle`'s "external call first, DB write only after success"
    ordering so a failed Vercel call never leaves the bundle in an
    inconsistent local state.

    Raises `VercelClientError` on failure — the caller (the `unpublish`
    view action) maps that to a 502, same as `deploy_bundle`. If the bundle
    was never deployed (no `public_slug` yet), there is no Vercel project to
    delete, so the Vercel call is skipped entirely.
    """
    if bundle.public_slug:
        client = build_vercel_client()
        client.delete_project(project_name_for_bundle(bundle))
    bundle.deactivate()
