from django.db import models

from apps.editor.models import SiteBundle


class VercelDeployment(models.Model):
    """One deployment attempt for a ``SiteBundle``. A bundle may accumulate
    several rows over time (redeploys after re-uploading assets); each
    successful deploy call creates a new row rather than mutating an
    existing one, so the deploy history stays auditable. ``project_id`` is
    Vercel's own id for the (deterministically named ``mq-{public_slug}``)
    project — a redeploy reuses the same project because the project name
    is stable, so ``project_id`` is expected to repeat across a bundle's
    rows while ``deployment_id`` is unique per row.

    Only ever created on a *successful* Vercel API call — see
    ``apps.vercel.services.deploy_bundle``'s docstring: a failed deploy call
    raises without creating a row, so there is never a partial/half-written
    deployment record for callers to trip over.
    """

    bundle = models.ForeignKey(SiteBundle, on_delete=models.CASCADE, related_name="deployments")
    project_id = models.CharField(max_length=255)
    deployment_id = models.CharField(max_length=255)
    url = models.URLField(max_length=500)
    # Raw `readyState` from the Vercel API (e.g. "READY", "INITIALIZING",
    # "ERROR") — stored as-is rather than remapped to a project-specific
    # vocabulary, so a future poll (`get_deployment`) can update it without
    # a translation layer.
    state = models.CharField(max_length=32)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.bundle_id}:{self.deployment_id}"
