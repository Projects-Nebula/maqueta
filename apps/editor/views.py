import uuid

from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.db.models import Max
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.projects.models import Project
from apps.vercel.client import VercelClientError
from apps.vercel.services import deploy_bundle, unpublish_bundle

from .asset_validation import BundleFile, BundleValidationError, resolve_entrypoint, validate_bundle
from .image_processing import ImageProcessingError, process_upload
from .models import (
    AuditEvent,
    BundleAsset,
    SiteBundle,
    Template,
    UploadedAsset,
    UserPalette,
    UserTemplate,
    UserTemplateRevision,
)
from .palettes import palette_catalog_for_client
from .rendering import public_page_html
from .serializers import (
    AuditEventSerializer,
    SiteBundleSerializer,
    UploadedAssetSerializer,
    UserPaletteSerializer,
    UserTemplateRevisionSerializer,
    UserTemplateSerializer,
)

# History grows unbounded otherwise — keep the most recent N per template.
REVISION_RETENTION_LIMIT = 20

# Per-user cap on stored wizard uploads (disk use, not just request cost).
MAX_UPLOADED_ASSETS_PER_USER = 50


@never_cache
@login_required
@ensure_csrf_cookie
def editor_view(request):
    """Serve the visual editor shell with the chosen template already inlined.

    ``?t=<slug>`` selects a base ``Template`` (global catalog); ``?ut=<id>``
    selects the current user's own ``UserTemplate`` (owner-scoped); ``?p=<id>``
    selects an owner-scoped ``Project``, autosaved via
    ``static/editor/autosave.js`` — its current content is its latest
    ``ProjectRevision`` if one exists, else the project's own (initially
    empty) ``state``. Its ``state`` is injected server-side (via
    ``json_script``) so the page arrives with the data already present — the
    client applies it synchronously, no fetch. A null/absent state means "use
    the editor's built-in default page". ``ensure_csrf_cookie`` sets the
    ``csrftoken`` cookie for the AI panel's API calls; ``never_cache`` keeps
    the per-query HTML from being reused for a different template.
    """
    slug = request.GET.get("t")
    ut_id = request.GET.get("ut")
    project_id = request.GET.get("p")
    state = None
    user_template_id = None
    if slug:
        state = Template.objects.filter(slug=slug).values_list("state", flat=True).first()
    elif ut_id and ut_id.isdigit():
        user_template = UserTemplate.objects.filter(owner=request.user, pk=ut_id).first()
        if user_template:
            state = user_template.state
            user_template_id = user_template.id
    elif project_id:
        try:
            uuid.UUID(project_id)
        except ValueError:
            project_id = None
        else:
            project = Project.objects.filter(owner=request.user, pk=project_id).first()
            if project:
                latest_revision = project.revisions.order_by("-version").first()
                state = latest_revision.state if latest_revision else project.state
            else:
                project_id = None
    return render(
        request,
        "editor/editor.html",
        {
            "template_state": state,
            "user_template_id": user_template_id,
            "project_id": project_id,
            "palette_catalog": palette_catalog_for_client(request.user.user_palettes.all()),
        },
    )


@login_required
def home_view(request):
    """Home: the base templates we curate."""
    return render(request, "editor/home.html", {"templates": Template.objects.all()})


@login_required
def gallery_view(request):
    """Gallery: the current user's saved templates."""
    return render(request, "editor/gallery.html", {"templates": request.user.user_templates.all()})


@login_required
@ensure_csrf_cookie
def template_wizard_view(request):
    """AI-guided flow to create a custom template from scratch.

    Fully client-driven (no server-side context needed): the wizard chats
    with the user, generates a tailored question form, loops on clarification
    if needed, then generates and saves a new UserTemplate via the existing
    /api/user-templates/ endpoint. ensure_csrf_cookie mirrors editor_view's
    reasoning — the page's fetch() calls to /api/ai/wizard/* and
    /api/user-templates/ need the csrftoken cookie set.
    """
    return render(
        request,
        "editor/template_wizard.html",
        {"palette_catalog": palette_catalog_for_client(request.user.user_palettes.all())},
    )


class PublicTemplateView(APIView):
    """GET /t/<slug>/ — the public, anonymous-accessible page for a
    published UserTemplate (FEATURE.md). Same 404 for "doesn't exist" and
    "not published" — never let a visitor distinguish the two, so an
    unpublished/private template can't be enumerated by slug guessing.
    Read-only: no editor script, no data-vjpb-path attributes, nothing
    mutates from here. Rate-limited like every other anonymous-facing
    endpoint in the project (ScopedRateThrottle already keys by IP for
    unauthenticated requests).
    """

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "public_template_view"

    @method_decorator(never_cache)
    def get(self, request, slug):
        user_template = UserTemplate.objects.filter(public_slug=slug, is_published=True).first()
        if not user_template:
            raise Http404
        html = public_page_html(
            user_template.state,
            title_fallback=user_template.name,
            analytics_template_slug=user_template.public_slug,
        )
        return HttpResponse(html)


# Sandbox WITHOUT allow-same-origin — the load-bearing control for
# PublicBundleAssetView (see its docstring and design.md's threat model).
# Do not add allow-same-origin to this policy.
_BUNDLE_SANDBOX_CSP = (
    "sandbox allow-scripts allow-forms allow-popups "
    "allow-popups-to-escape-sandbox allow-top-navigation-by-user-activation"
)


class PublicBundleAssetView(APIView):
    """GET /s/<slug>/<path> — serves a maqueta-hosted SiteBundle's assets
    verbatim from BundleAsset rows, never the filesystem (see
    apps.editor.asset_validation's path-hardening doctrine — every stored
    `BundleAsset.path` was already validated at ingestion, so an exact DB
    lookup on the requested path is the whole traversal defense; there is
    no filesystem join to escape). Mirrors PublicTemplateView's "same 404
    for missing vs. unpublished" doctrine: unknown slug, an inactive or
    never-published bundle, and an unknown path are all indistinguishable
    404s (see design.md's threat matrix) — no enumeration signal either
    way.

    SECURITY-CRITICAL: seller HTML/JS is admitted verbatim at ingestion
    (deploy-as-is doctrine) and now served from maqueta's OWN origin, so
    every response here sets its own
    `Content-Security-Policy: sandbox ...` WITHOUT `allow-same-origin`.
    `sandbox` alone forces the document into an opaque origin: no
    document.cookie/localStorage access, no same-site cookies attached to
    its own requests, no readable responses from /api/..., no service
    worker registration — see design.md's "Same-origin isolation via CSP
    sandbox" decision for the full threat writeup. Do NOT add
    allow-same-origin here; that reopens the ambient-session-theft path
    this header exists to close. The view also never touches
    `request.session` and strips any cookies from the response, so no
    maqueta session is ever exposed on this path.
    """

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "bundle_serve"

    @method_decorator(never_cache)
    def get(self, request, slug, asset_path=""):
        bundle = SiteBundle.objects.filter(
            public_slug=slug, is_active=True, is_hosted_locally=True
        ).first()
        if not bundle:
            raise Http404

        resolved_path = asset_path or bundle.entrypoint_path
        asset = BundleAsset.objects.filter(bundle=bundle, path=resolved_path).first()
        if not asset:
            raise Http404

        response = FileResponse(asset.file.open("rb"), content_type=asset.content_type)
        response["Content-Security-Policy"] = _BUNDLE_SANDBOX_CSP
        response["X-Content-Type-Options"] = "nosniff"
        response["Referrer-Policy"] = "no-referrer"
        response["Cross-Origin-Opener-Policy"] = "same-origin"
        response.cookies.clear()
        return response


class UserPaletteViewSet(viewsets.ModelViewSet):
    """CRUD for the current user's reusable palette catalog."""

    serializer_class = UserPaletteSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return UserPalette.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class UserTemplateViewSet(viewsets.ModelViewSet):
    serializer_class = UserTemplateSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return UserTemplate.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        instance = serializer.save(owner=self.request.user)
        AuditEvent.record(
            owner=self.request.user,
            action=AuditEvent.Action.TEMPLATE_CREATE,
            target_type="user_template",
            target_id=instance.pk,
            metadata={"name": instance.name},
        )

    def perform_update(self, serializer):
        # Snapshot the state being replaced so the update can be rolled back
        # later — but only if it actually changes; a no-op save (e.g.
        # restoring to the version that's already current) shouldn't pad the
        # history with an identical entry.
        instance = serializer.instance
        new_state = serializer.validated_data.get("state", instance.state)
        if new_state != instance.state:
            next_version = (instance.revisions.aggregate(top=Max("version"))["top"] or 0) + 1
            UserTemplateRevision.objects.create(
                user_template=instance, version=next_version, state=instance.state
            )
            keep_ids = instance.revisions.order_by("-version").values_list("pk", flat=True)[
                :REVISION_RETENTION_LIMIT
            ]
            instance.revisions.exclude(pk__in=list(keep_ids)).delete()
            AuditEvent.record(
                owner=self.request.user,
                action=AuditEvent.Action.TEMPLATE_SAVE,
                target_type="user_template",
                target_id=instance.pk,
                metadata={"name": instance.name, "version": next_version},
            )
        serializer.save()

    @action(detail=True, methods=["get"])
    def revisions(self, request, pk=None):
        user_template = self.get_object()  # already owner-scoped via get_queryset
        serializer = UserTemplateRevisionSerializer(user_template.revisions.all(), many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["delete"], url_path=r"revisions/(?P<revision_id>[^/.]+)")
    def delete_revision(self, request, pk=None, revision_id=None):
        user_template = self.get_object()  # already owner-scoped via get_queryset
        # Scoped through this instance's own revisions manager: a revision_id
        # belonging to another user's template simply won't match (0 deleted).
        deleted, _ = user_template.revisions.filter(pk=revision_id).delete()
        if not deleted:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        user_template = self.get_object()  # already owner-scoped via get_queryset
        user_template.publish()
        return Response(UserTemplateSerializer(user_template).data)

    @action(detail=True, methods=["post"])
    def unpublish(self, request, pk=None):
        user_template = self.get_object()  # already owner-scoped via get_queryset
        user_template.unpublish()
        return Response(UserTemplateSerializer(user_template).data)


class AuditEventListView(generics.ListAPIView):
    """GET /api/audit-events/ — the requesting user's own recent audit trail
    (which AI instruction/save produced a given change), read-only."""

    serializer_class = AuditEventSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Retention (AuditEvent.record) already caps this per owner — the
        # slice here is defensive, not the primary bound.
        return AuditEvent.objects.filter(owner=self.request.user)[: AuditEvent.RETENTION_LIMIT]


class WizardImageUploadView(APIView):
    """/api/wizard-images/ — the wizard's re-encoded image uploads.

    GET lists the requesting user's own previously uploaded assets (the
    editor's "Imagen" picker reuses these, see FEATURE.md-style
    available_products pattern — owner-scoped, never another user's).
    POST resizes/re-encodes a new upload. Never stores the raw upload;
    always re-encoded via image_processing.process_upload, which also
    bounds dimensions/size so a heavy upload can't affect any other flow
    (request timeout, disk, memory).
    """

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "wizard_upload"

    def get(self, request):
        assets = request.user.uploaded_assets.order_by("-created_at")[:MAX_UPLOADED_ASSETS_PER_USER]
        return Response(UploadedAssetSerializer(assets, many=True).data)

    def post(self, request):
        upload = request.FILES.get("file")
        if not upload:
            return Response({"error": "invalid_input", "detail": "no file provided"}, status=400)

        if request.user.uploaded_assets.count() >= MAX_UPLOADED_ASSETS_PER_USER:
            return Response({"error": "too_many_assets"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            encoded, _content_type, width, height, placeholder_color = process_upload(upload.read())
        except ImageProcessingError as exc:
            return Response({"error": "invalid_image", "detail": str(exc)}, status=400)

        asset = UploadedAsset(
            owner=request.user, width=width, height=height, placeholder_color=placeholder_color
        )
        asset.file.save("upload.jpg", ContentFile(encoded), save=True)
        return Response(
            UploadedAssetSerializer(asset).data,
            status=status.HTTP_201_CREATED,
        )

    def delete(self, request, asset_id):
        """Delete an uploaded asset that the wizard no longer uses."""
        asset = request.user.uploaded_assets.filter(pk=asset_id).first()
        if not asset:
            return Response(status=status.HTTP_404_NOT_FOUND)
        asset.file.delete(save=False)
        asset.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class BundleViewSet(viewsets.ModelViewSet):
    """/api/editor/bundles/ — upload and deploy a "site bundle" (an
    HTML+assets upload deployed as-is; see design: vercel-bundle-deploy).

    POST (create) ingests a bundle: every multipart field whose key is not
    ``name`` is treated as one file, keyed by its bundle-relative path (e.g.
    a field named ``assets/logo.png``) — this is the same contract the
    folder-picker UI (PR4) will produce by appending each
    ``file.webkitRelativePath`` as the field name. All ingestion goes
    through ``asset_validation.validate_bundle()`` once; nothing here
    re-validates.

    POST .../<id>/deploy/ ("Publicar tal cual") deploys the bundle's
    already-validated assets verbatim via
    ``apps.vercel.services.deploy_bundle()``. The other post-upload action,
    "Editar antes de publicar" (.../convert/), is an explicit 501 stub in
    this change — node conversion is site-bundle-import's scope (PR3/4 of
    that change, not built here); see design.md non-goals.
    """

    serializer_class = SiteBundleSerializer
    permission_classes = [IsAuthenticated]
    # MultiPartParser for create() (file upload); JSONParser for deploy()'s
    # {"target": ...} body — parser_classes is viewset-wide, not per-action.
    parser_classes = [MultiPartParser, JSONParser]
    http_method_names = ["get", "post", "head", "options"]

    # Scoped per-action rather than one throttle_scope for the whole
    # viewset: upload and deploy are independent rate limits (design.md),
    # and read-only actions (list/retrieve) are not scope-limited at all.
    _THROTTLE_SCOPES = {"create": "bundle_upload", "deploy": "bundle_deploy"}

    def get_throttles(self):
        scope = self._THROTTLE_SCOPES.get(self.action)
        if not scope:
            return []
        self.throttle_scope = scope
        return [ScopedRateThrottle()]

    def get_queryset(self):
        return SiteBundle.objects.filter(owner=self.request.user)

    def create(self, request, *args, **kwargs):
        name = (request.data.get("name") or "").strip()[:120] or "site"
        bundle_files = [
            BundleFile(path=path, data=upload.read()) for path, upload in request.FILES.items()
        ]
        if not bundle_files:
            return Response(
                {"error": "missing_entrypoint", "detail": "no files provided"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            validated_assets = validate_bundle(bundle_files)
        except BundleValidationError as exc:
            return Response({"error": exc.code, "detail": str(exc)}, status=400)

        requested_entrypoint = (request.data.get("entrypoint") or "").strip() or None
        try:
            entrypoint_path = resolve_entrypoint(validated_assets, requested_entrypoint)
        except BundleValidationError as exc:
            body = {"error": exc.code, "detail": str(exc)}
            if exc.candidates is not None:
                body["candidates"] = exc.candidates
            return Response(body, status=400)

        bundle = SiteBundle.objects.create(
            owner=request.user, name=name, entrypoint_path=entrypoint_path
        )
        for asset in validated_assets:
            bundle_asset = BundleAsset(
                bundle=bundle,
                path=asset.path,
                content_type=asset.content_type,
                byte_size=len(asset.data),
            )
            bundle_asset.file.save(
                asset.path.rsplit("/", 1)[-1], ContentFile(asset.data), save=False
            )
            bundle_asset.save()

        return Response(
            SiteBundleSerializer(bundle).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def deploy(self, request, pk=None):
        """ "Publicar tal cual". ``target`` picks the deploy destination —
        defaults to "vercel" so existing callers (no body) keep their prior
        behavior unchanged. "maqueta" publishes first-party via
        PublicBundleAssetView, gated purely by SiteBundle.is_hosted_locally
        (see design: deploy-target choice gated by explicit publish
        action) — uploading a bundle never makes it servable on its own.
        """
        bundle = self.get_object()  # already owner-scoped via get_queryset
        target = (request.data.get("target") or "vercel").strip().lower()

        if target == "maqueta":
            bundle.ensure_public_slug()
            bundle.is_hosted_locally = True
            bundle.save(update_fields=["is_hosted_locally", "updated_at"])
            url = request.build_absolute_uri(f"/s/{bundle.public_slug}/")
            return Response({"target": "maqueta", "url": url}, status=status.HTTP_201_CREATED)

        if target == "vercel":
            # Non-index.html entrypoints are only servable via the
            # maqueta-hosted target in this slice (see design: Vercel
            # deploy path continues requiring index.html).
            if bundle.entrypoint_path != "index.html":
                return Response({"error": "vercel_requires_index"}, status=400)
            try:
                deployment = deploy_bundle(bundle)
            except VercelClientError:
                return Response({"error": "deploy_failed"}, status=502)
            return Response(
                {"id": deployment.pk, "url": deployment.url, "state": deployment.state},
                status=status.HTTP_201_CREATED,
            )

        return Response({"error": "invalid_target"}, status=400)

    @action(detail=True, methods=["post"])
    def convert(self, request, pk=None):
        """ "Editar antes de publicar" — hand-off to site-bundle-import's
        node converter. Not built in this change (explicit non-goal); this
        stub exists so the two-action UI always gets a clear, non-silent
        response instead of a 404 for the second action.
        """
        self.get_object()  # 404s for a nonexistent/non-owned bundle first
        return Response(
            {"error": "conversion_unavailable", "detail": "not implemented yet"},
            status=status.HTTP_501_NOT_IMPLEMENTED,
        )

    @action(detail=True, methods=["post"])
    def unpublish(self, request, pk=None):
        """Manual takedown — allowed for the bundle's owner or staff.
        Looked up directly by pk (not via `get_queryset()`, which is
        owner-scoped): staff taking a bundle down does not own it."""
        bundle = get_object_or_404(SiteBundle, pk=pk)
        if bundle.owner != request.user and not request.user.is_staff:
            raise PermissionDenied()
        try:
            unpublish_bundle(bundle)
        except VercelClientError:
            return Response({"error": "unpublish_failed"}, status=502)
        return Response(SiteBundleSerializer(bundle).data)
