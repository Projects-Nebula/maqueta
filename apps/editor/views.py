import uuid

from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.db.models import Max
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.projects.models import Project

from .image_processing import ImageProcessingError, process_upload
from .models import Template, UploadedAsset, UserTemplate, UserTemplateRevision
from .serializers import (
    UploadedAssetSerializer,
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
    return render(request, "editor/template_wizard.html", {})


class UserTemplateViewSet(viewsets.ModelViewSet):
    serializer_class = UserTemplateSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return UserTemplate.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

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


class WizardImageUploadView(APIView):
    """POST /api/wizard/upload-image/ — resize/re-encode an image for the AI
    wizard to reference in a generated page (see WizardGenerateRequestSerializer's
    `assets` field). Never stores the raw upload; always re-encoded via
    image_processing.process_upload, which also bounds dimensions/size so a
    heavy upload can't affect any other flow (request timeout, disk, memory).
    """

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "wizard_upload"

    def post(self, request):
        upload = request.FILES.get("file")
        if not upload:
            return Response({"error": "invalid_input", "detail": "no file provided"}, status=400)

        if request.user.uploaded_assets.count() >= MAX_UPLOADED_ASSETS_PER_USER:
            return Response({"error": "too_many_assets"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            encoded, _content_type, width, height = process_upload(upload.read())
        except ImageProcessingError as exc:
            return Response({"error": "invalid_image", "detail": str(exc)}, status=400)

        asset = UploadedAsset(owner=request.user, width=width, height=height)
        asset.file.save("upload.jpg", ContentFile(encoded), save=True)
        return Response(
            UploadedAssetSerializer(asset).data,
            status=status.HTTP_201_CREATED,
        )
