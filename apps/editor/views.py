from django.contrib.auth.decorators import login_required
from django.db.models import Max
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Template, UserTemplate, UserTemplateRevision
from .serializers import UserTemplateRevisionSerializer, UserTemplateSerializer

# History grows unbounded otherwise — keep the most recent N per template.
REVISION_RETENTION_LIMIT = 20


@never_cache
@login_required
@ensure_csrf_cookie
def editor_view(request):
    """Serve the visual editor shell with the chosen template already inlined.

    ``?t=<slug>`` selects a base ``Template`` (global catalog); ``?ut=<id>``
    selects the current user's own ``UserTemplate`` (owner-scoped). Its
    ``state`` is injected server-side (via ``json_script``) so the page
    arrives with the data already present — the client applies it
    synchronously, no fetch. A null/absent state means "use the editor's
    built-in default page". ``ensure_csrf_cookie`` sets the ``csrftoken``
    cookie for the AI panel's API calls; ``never_cache`` keeps the per-query
    HTML from being reused for a different template.
    """
    slug = request.GET.get("t")
    ut_id = request.GET.get("ut")
    state = None
    user_template_id = None
    if slug:
        state = Template.objects.filter(slug=slug).values_list("state", flat=True).first()
    elif ut_id and ut_id.isdigit():
        user_template = UserTemplate.objects.filter(owner=request.user, pk=ut_id).first()
        if user_template:
            state = user_template.state
            user_template_id = user_template.id
    return render(
        request,
        "editor/editor.html",
        {"template_state": state, "user_template_id": user_template_id},
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
