"""Token-free serializers for the Hotmart API surface (see openspec design:
hotmart-developer-credentials-pivot, "Security Approach" — no
credential/token/ciphertext ever appears in a response).
"""

from __future__ import annotations

from rest_framework import serializers

from apps.ai_assistant.sanitize import MAX_ASSETS
from apps.ai_assistant.serializers import AssetInputSerializer
from apps.editor.models import UserTemplate
from apps.editor.palettes import PALETTE_ID_RE, get_palette_preset

from .models import HotmartConnection, HotmartProductLink


class HotmartCredentialsSerializer(serializers.Serializer):
    """Write-only input for POST /api/hotmart/credentials/. Both fields
    are optional (blank means "keep the existing stored value" — spec:
    "Rotating one credential") — CredentialsView resolves the blank-keeps-
    existing merge, this serializer only validates shape/presence of
    fields."""

    client_id = serializers.CharField(write_only=True, required=False, allow_blank=True, default="")
    client_secret = serializers.CharField(
        write_only=True, required=False, allow_blank=True, default=""
    )


class HotmartConnectionSerializer(serializers.ModelSerializer):
    """Read-only status serializer: `connected` is always True for any row
    that exists (a disconnect deletes the row entirely), so the client
    only ever needs to check whether the request for this resource 404s
    or succeeds — this shape matches the spec's "No Token Exposure"
    requirement (no token, no ciphertext, ever)."""

    connected = serializers.SerializerMethodField()

    class Meta:
        model = HotmartConnection
        fields = ["connected", "hotmart_account_id", "expires_at", "connected_at"]
        read_only_fields = fields

    def get_connected(self, obj):
        return True


class HotmartProductLinkSerializer(serializers.ModelSerializer):
    """Metadata-only link between a Hotmart product and a landing (design:
    "no local product mirror" — this row stores only display metadata, no
    price/checkout logic)."""

    user_template = serializers.PrimaryKeyRelatedField(queryset=UserTemplate.objects.all())

    class Meta:
        model = HotmartProductLink
        fields = [
            "id",
            "user_template",
            "hotmart_product_id",
            "product_name",
            "checkout_url",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "status", "created_at", "updated_at"]

    def validate_user_template(self, value):
        request = self.context.get("request")
        if request is not None and value.owner_id != request.user.id:
            raise serializers.ValidationError("user_template must be one of your own templates")
        return value

    def validate_checkout_url(self, value):
        if value and not value.startswith("https://"):
            raise serializers.ValidationError("checkout_url must use https")
        return value

    def validate(self, attrs):
        connection = self.context["connection"]
        instance_pk = self.instance.pk if self.instance else None

        user_template = attrs.get("user_template")
        if user_template is not None:
            clash = HotmartProductLink.objects.filter(user_template=user_template).exclude(
                pk=instance_pk
            )
            if clash.exists():
                raise serializers.ValidationError(
                    {"user_template": "this landing is already linked to a product"}
                )

        hotmart_product_id = attrs.get("hotmart_product_id")
        if hotmart_product_id:
            clash = HotmartProductLink.objects.filter(
                connection=connection, hotmart_product_id=hotmart_product_id
            ).exclude(pk=instance_pk)
            if clash.exists():
                raise serializers.ValidationError(
                    {"hotmart_product_id": "this product is already linked to a landing"}
                )

        return attrs


# --- Landing generation request --------------------------------------------

# Fixed 3-question form (design decision "Fixed 3 questions,
# server-allowlisted"): the server rejects any other answer key rather than
# accepting a free-form dict, since Hotmart already supplies name/price and
# only "who / what promise / what's included" carry real content the API
# cannot give.
LANDING_ALLOWED_ANSWER_KEYS = {"audience", "promise", "offer_details"}
LANDING_REQUIRED_ANSWER_KEYS = {"audience", "promise"}
MAX_LANDING_ANSWER_LENGTH = 2000


def _validate_landing_answers(answers) -> dict:
    if not isinstance(answers, dict):
        raise serializers.ValidationError({"answers": "must be an object"})

    unknown = set(answers) - LANDING_ALLOWED_ANSWER_KEYS
    if unknown:
        raise serializers.ValidationError({"answers": f"unknown answer key(s): {sorted(unknown)}"})

    for key, value in answers.items():
        if not isinstance(value, str) or len(value) > MAX_LANDING_ANSWER_LENGTH:
            raise serializers.ValidationError({"answers": f"invalid answer value for {key}"})

    missing = {key for key in LANDING_REQUIRED_ANSWER_KEYS if not answers.get(key, "").strip()}
    if missing:
        raise serializers.ValidationError(
            {"answers": f"missing required answer(s): {sorted(missing)}"}
        )

    return {key: value.strip() for key, value in answers.items()}


class LandingGenerateRequestSerializer(serializers.Serializer):
    """POST body for `ProductLandingGenerateView` (design: "Combined
    Generate-And-Link Endpoint"). `checkout_url` reuses the same https-only
    rule as `HotmartProductLinkSerializer.validate_checkout_url` — no
    upstream source exists, so it is a manual, optional field."""

    answers = serializers.DictField()
    checkout_url = serializers.CharField(
        max_length=500, required=False, allow_blank=True, default=""
    )
    assets = serializers.ListField(
        child=AssetInputSerializer(), required=False, default=list, max_length=MAX_ASSETS
    )
    palette_id = serializers.CharField(
        max_length=64, required=False, allow_blank=True, allow_null=True, default=None
    )

    def validate_answers(self, value):
        return _validate_landing_answers(value)

    def validate_checkout_url(self, value):
        if value and not value.startswith("https://"):
            raise serializers.ValidationError("checkout_url must use https")
        return value

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
