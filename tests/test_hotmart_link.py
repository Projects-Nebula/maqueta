"""RED tests for product-to-landing linking (see spec's
"hotmart-product-landing-link" domain: 1-to-1 enforcement, owner scoping,
metadata-only)."""

import pytest

from apps.editor.models import UserTemplate
from apps.hotmart.models import HotmartConnection, HotmartProductLink

pytestmark = pytest.mark.django_db

LINKS_URL = "/api/hotmart/links/"


def _state():
    return {"document": {"body": {"children": []}}}


def _connection(user):
    connection = HotmartConnection.objects.create(owner=user)
    connection.set_tokens(access="a", expires_in=3600)
    connection.save()
    return connection


def _template(owner, name="Landing"):
    return UserTemplate.objects.create(owner=owner, name=name, state=_state())


class TestCreateLink:
    def test_links_a_product_to_a_landing(self, api, user):
        _connection(user)
        template = _template(user)

        response = api.post(
            LINKS_URL,
            {
                "user_template": template.id,
                "hotmart_product_id": "prod-1",
                "product_name": "My Product",
                "checkout_url": "https://hotmart.example.com/checkout/prod-1",
            },
        )

        assert response.status_code == 201
        link = HotmartProductLink.objects.get(user_template=template)
        assert link.hotmart_product_id == "prod-1"
        assert link.status == HotmartProductLink.Status.ACTIVE

    def test_requires_a_connection(self, api, user):
        template = _template(user)

        response = api.post(
            LINKS_URL,
            {
                "user_template": template.id,
                "hotmart_product_id": "prod-1",
                "checkout_url": "https://hotmart.example.com/checkout/prod-1",
            },
        )

        assert response.status_code == 404

    def test_rejects_second_link_to_same_product(self, api, user):
        connection = _connection(user)
        first_template = _template(user, name="Landing A")
        second_template = _template(user, name="Landing B")
        HotmartProductLink.objects.create(
            connection=connection,
            user_template=first_template,
            hotmart_product_id="prod-1",
            checkout_url="https://hotmart.example.com/checkout/prod-1",
        )

        response = api.post(
            LINKS_URL,
            {
                "user_template": second_template.id,
                "hotmart_product_id": "prod-1",
                "checkout_url": "https://hotmart.example.com/checkout/prod-1",
            },
        )

        assert response.status_code == 400
        assert HotmartProductLink.objects.filter(hotmart_product_id="prod-1").count() == 1

    def test_rejects_second_link_for_same_landing(self, api, user):
        connection = _connection(user)
        template = _template(user)
        HotmartProductLink.objects.create(
            connection=connection,
            user_template=template,
            hotmart_product_id="prod-1",
            checkout_url="https://hotmart.example.com/checkout/prod-1",
        )

        response = api.post(
            LINKS_URL,
            {
                "user_template": template.id,
                "hotmart_product_id": "prod-2",
                "checkout_url": "https://hotmart.example.com/checkout/prod-2",
            },
        )

        assert response.status_code == 400
        assert HotmartProductLink.objects.filter(user_template=template).count() == 1

    def test_rejects_landing_owned_by_another_user(self, api, user, other_user):
        _connection(user)
        other_template = _template(other_user)

        response = api.post(
            LINKS_URL,
            {
                "user_template": other_template.id,
                "hotmart_product_id": "prod-1",
                "checkout_url": "https://hotmart.example.com/checkout/prod-1",
            },
        )

        assert response.status_code == 400
        assert not HotmartProductLink.objects.filter(user_template=other_template).exists()

    def test_rejects_non_https_checkout_url(self, api, user):
        _connection(user)
        template = _template(user)

        response = api.post(
            LINKS_URL,
            {
                "user_template": template.id,
                "hotmart_product_id": "prod-1",
                "checkout_url": "http://insecure.example.com/checkout",
            },
        )

        assert response.status_code == 400


class TestLinkOwnerScoping:
    def test_cross_owner_link_is_not_found(self, api, other_api, user, other_user):
        connection = _connection(other_user)
        template = _template(other_user)
        link = HotmartProductLink.objects.create(
            connection=connection,
            user_template=template,
            hotmart_product_id="prod-1",
            checkout_url="https://hotmart.example.com/checkout/prod-1",
        )

        response = api.delete(f"{LINKS_URL}{link.id}/")

        assert response.status_code == 404
        assert HotmartProductLink.objects.filter(pk=link.pk).exists()

    def test_unlink_does_not_unpublish(self, api, user):
        connection = _connection(user)
        template = _template(user)
        template.publish()
        link = HotmartProductLink.objects.create(
            connection=connection,
            user_template=template,
            hotmart_product_id="prod-1",
            checkout_url="https://hotmart.example.com/checkout/prod-1",
        )

        response = api.delete(f"{LINKS_URL}{link.id}/")

        assert response.status_code == 204
        template.refresh_from_db()
        assert template.is_published is True
        assert not HotmartProductLink.objects.filter(pk=link.pk).exists()

    def test_list_only_shows_own_links(self, api, other_api, user, other_user):
        my_connection = _connection(user)
        my_template = _template(user)
        HotmartProductLink.objects.create(
            connection=my_connection,
            user_template=my_template,
            hotmart_product_id="prod-1",
            checkout_url="https://hotmart.example.com/checkout/prod-1",
        )
        other_connection = _connection(other_user)
        other_template = _template(other_user)
        HotmartProductLink.objects.create(
            connection=other_connection,
            user_template=other_template,
            hotmart_product_id="prod-2",
            checkout_url="https://hotmart.example.com/checkout/prod-2",
        )

        response = api.get(LINKS_URL)

        assert response.status_code == 200
        ids = {row["hotmart_product_id"] for row in response.data}
        assert ids == {"prod-1"}
