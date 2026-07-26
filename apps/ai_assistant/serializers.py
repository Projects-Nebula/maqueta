"""Validation of the untrusted transform request coming from the browser."""

import json

from django.conf import settings
from rest_framework import serializers

from apps.editor.palettes import PALETTE_ID_RE, get_palette_preset

from .html_import import MAX_IMPORT_HTML_LENGTH
from .sanitize import (
    ASSET_URL_PREFIX,
    MAX_ASSETS,
    SanitizationError,
    sanitize_context_node,
)


class NonNegativeIntListField(serializers.ListField):
    child = serializers.IntegerField(min_value=0)


class HistoryMessageSerializer(serializers.Serializer):
    """One prior chat turn. Untrusted text — bounded, never executed."""

    role = serializers.ChoiceField(choices=["user", "assistant"])
    content = serializers.CharField(max_length=2000, allow_blank=True, trim_whitespace=False)


class TransformRequestSerializer(serializers.Serializer):
    instruction = serializers.CharField(max_length=2000, trim_whitespace=True)
    selected_path = NonNegativeIntListField(required=False, allow_null=True)
    selected_node = serializers.DictField(required=False, allow_null=True)
    parent_context = serializers.DictField(required=False, default=dict)
    sibling_context = serializers.ListField(required=False, default=list)
    design_variables = serializers.DictField(required=False, default=dict)
    page_summary = serializers.DictField(required=False, default=dict)
    # Real current top-level body children (index, tag, class) — lets the
    # model target delete/replace paths that actually exist instead of
    # guessing indices from a stale mental model. Bounded like sibling_context.
    body_outline = serializers.ListField(required=False, default=list, max_length=40)
    global_mode = serializers.BooleanField(required=False, default=False)
    # Prior conversation turns so the assistant has context ("ahora hazlo más
    # grande"). Capped in count and length; counts toward the total size limit.
    history = serializers.ListField(
        child=HistoryMessageSerializer(), required=False, default=list, max_length=12
    )

    def validate(self, attrs):
        # Total payload size cap (defence against oversized inputs).
        size = len(json.dumps(self.initial_data, ensure_ascii=False))
        if size > settings.AI_MAX_INPUT_CHARACTERS:
            raise serializers.ValidationError("payload too large")

        if not attrs.get("global_mode") and not attrs.get("selected_node"):
            raise serializers.ValidationError("selected_node is required unless global_mode is set")

        node = attrs.get("selected_node")
        if node:
            try:
                attrs["selected_node"] = sanitize_context_node(node)
            except SanitizationError as exc:
                raise serializers.ValidationError({"selected_node": str(exc)}) from exc
        return attrs


class ImportHtmlRequestSerializer(serializers.Serializer):
    html = serializers.CharField(max_length=MAX_IMPORT_HTML_LENGTH, trim_whitespace=True)


# --- Template-creation wizard requests --------------------------------------

MAX_WIZARD_ANSWERS = 30
MAX_ANSWER_KEY_LENGTH = 100
MAX_ANSWER_VALUE_LENGTH = 2000


def _validate_answers(answers) -> None:
    if not isinstance(answers, dict):
        raise serializers.ValidationError({"answers": "must be an object"})
    if len(answers) > MAX_WIZARD_ANSWERS:
        raise serializers.ValidationError({"answers": "too many answers"})
    for key, value in answers.items():
        if not isinstance(key, str) or not key or len(key) > MAX_ANSWER_KEY_LENGTH:
            raise serializers.ValidationError({"answers": f"invalid answer key: {key}"})
        if not isinstance(value, str) or len(value) > MAX_ANSWER_VALUE_LENGTH:
            raise serializers.ValidationError({"answers": f"invalid answer value for {key}"})


class WizardQuestionsRequestSerializer(serializers.Serializer):
    description = serializers.CharField(max_length=2000, trim_whitespace=True)
    history = serializers.ListField(
        child=HistoryMessageSerializer(), required=False, default=list, max_length=12
    )

    def validate(self, attrs):
        size = len(json.dumps(self.initial_data, ensure_ascii=False))
        if size > settings.AI_MAX_INPUT_CHARACTERS:
            raise serializers.ValidationError("payload too large")
        return attrs


class WizardReviewRequestSerializer(serializers.Serializer):
    description = serializers.CharField(max_length=2000, trim_whitespace=True)
    answers = serializers.DictField()
    # The clarification loop can legitimately run several rounds — capped
    # higher than the edit-transform history, still bounded.
    history = serializers.ListField(
        child=HistoryMessageSerializer(), required=False, default=list, max_length=20
    )

    def validate(self, attrs):
        size = len(json.dumps(self.initial_data, ensure_ascii=False))
        if size > settings.AI_MAX_INPUT_CHARACTERS:
            raise serializers.ValidationError("payload too large")
        _validate_answers(attrs.get("answers"))
        return attrs


class AssetInputSerializer(serializers.Serializer):
    """An image the user already uploaded (see WizardImageUploadView) that
    the AI may reference in the generated page's state.assets."""

    id = serializers.CharField(max_length=50)
    url = serializers.CharField(max_length=500)
    width = serializers.IntegerField(min_value=1)
    height = serializers.IntegerField(min_value=1)

    def validate_url(self, value):
        if not value.startswith(ASSET_URL_PREFIX):
            raise serializers.ValidationError("must be an uploaded asset URL")
        return value


class WizardGenerateRequestSerializer(WizardReviewRequestSerializer):
    """Same accumulated context as the review step, once it says ready."""

    assets = serializers.ListField(
        child=AssetInputSerializer(), required=False, default=list, max_length=MAX_ASSETS
    )
    palette_id = serializers.CharField(
        max_length=64, required=False, allow_blank=True, allow_null=True, default=None
    )

    def validate_palette_id(self, value):
        if value in (None, ""):
            return None
        if get_palette_preset(value) is not None:
            return value
        request = self.context.get("request")
        if not PALETTE_ID_RE.fullmatch(value) or not request:
            raise serializers.ValidationError("unknown palette preset")
        if not request.user.user_palettes.filter(slug=value).exists():
            raise serializers.ValidationError("unknown palette preset")
        return value
