"""Deploy a validated `SiteBundle` to its own isolated Vercel project.

See design.md's "One Vercel project per SiteBundle" decision: the project
name is deterministic (`mq-{public_slug}`), so calling `create_deployment`
again for the same bundle naturally redeploys into the same project — no
separate "does a project already exist" check is needed.
"""

from __future__ import annotations

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
    """Delegates to SiteBundle.ensure_public_slug() — the slug is shared by
    both deploy targets (Vercel and maqueta-hosted), so it lives on the
    model rather than being duplicated here. Kept as a thin wrapper so this
    module's other functions don't need to change their call sites."""
    return bundle.ensure_public_slug()


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
    inconsistent local state. Also clears `is_hosted_locally` regardless of
    Vercel deployment state, taking down the maqueta-hosted path too.

    Raises `VercelClientError` on failure — the caller (the `unpublish`
    view action) maps that to a 502, same as `deploy_bundle`.

    Guarded on `bundle.deployments.exists()`, NOT merely on `public_slug`
    being set (bug fix — see design: unpublish must stop calling Vercel for
    maqueta-only bundles). A maqueta-only publish sets `public_slug` (it's
    shared with the Vercel path) without ever creating a Vercel project, so
    guarding on `public_slug` alone would call Vercel for a project that
    never existed and 502 on `unpublish`.
    """
    if bundle.deployments.exists():
        client = build_vercel_client()
        client.delete_project(project_name_for_bundle(bundle))
    bundle.deactivate()
    bundle.unpublish_locally()
