"""Reset the local database and populate deterministic demo data."""

from __future__ import annotations

import io
import os
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management import BaseCommand, CommandError, call_command
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify
from PIL import Image, ImageDraw

from apps.analytics.models import AnalyticsEvent, AnalyticsSession, AnalyticsVisitor
from apps.editor.models import (
    Template,
    UploadedAsset,
    UserPalette,
    UserTemplate,
    UserTemplateRevision,
)
from apps.editor.palettes import PALETTE_PRESETS
from apps.projects.models import Project, ProjectRevision
from apps.storefront.models import Order, PaymentGatewayConfig, Product
from apps.storefront.payments import GATEWAY_CHOICES

DEMO_USERNAME = os.environ.get("MOCKUP_USERNAME", "demo")
DEMO_EMAIL = os.environ.get("MOCKUP_EMAIL", "demo@example.com")
DEMO_PASSWORD = os.environ.get("MOCKUP_PASSWORD", "demo12345")

DOCUMENT_SETTINGS = {
    "strict": True,
    "escapeText": True,
    "allowRawHtml": False,
    "allowInlineScripts": False,
    "requireImageAlt": True,
    "requireUniqueIds": True,
}
DEMO_RULES = [
    {"selector": "*", "declarations": {"box-sizing": "border-box"}},
    {
        "selector": "body",
        "declarations": {
            "margin": "0",
            "color": "var(--color-text)",
            "background": "var(--color-background)",
            "font-family": "var(--font-primary)",
            "line-height": "1.5",
        },
    },
    {
        "selector": "main",
        "declarations": {"max-width": "1100px", "margin": "0 auto", "padding": "48px 24px"},
    },
    {
        "selector": "header",
        "declarations": {"display": "flex", "flex-direction": "column", "gap": "12px"},
    },
    {
        "selector": "h1",
        "declarations": {"font-size": "clamp(36px, 7vw, 72px)", "margin": "0"},
    },
    {"selector": "p", "declarations": {"max-width": "680px"}},
    {
        "selector": "a",
        "declarations": {
            "display": "inline-block",
            "background": "var(--color-primary)",
            "color": "var(--color-surface)",
            "padding": "12px 20px",
            "border-radius": "999px",
            "text-decoration": "none",
            "font-weight": "700",
        },
    },
    {
        "selector": "img",
        "declarations": {
            "width": "100%",
            "max-height": "420px",
            "object-fit": "cover",
            "border-radius": "20px",
        },
    },
]


def _preset(preset_id: str) -> dict:
    return next(preset for preset in PALETTE_PRESETS if preset["id"] == preset_id)


def _text(value: str) -> dict:
    return {"type": "text", "value": value}


def _element(tag: str, children: list[dict] | None = None, **attributes) -> dict:
    return {
        "type": "element",
        "tag": tag,
        "attributes": attributes,
        "children": children or [],
    }


def _page_state(title: str, preset: dict, image_url: str | None = None) -> dict:
    slug = slugify(title) or "pagina"
    body_children = [
        _element(
            "header",
            [
                _element("p", [_text("MAQUETA / DEMO")]),
                _element("h1", [_text(title)]),
                _element("p", [_text("Contenido de ejemplo para explorar el editor visual.")]),
            ],
        )
    ]
    assets = {}
    if image_url:
        assets[f"{slug}-hero"] = {"url": image_url, "width": 1200, "height": 800}
        body_children.append(_element("img", [], src=image_url, alt=f"Imagen de {title}"))
    body_children.extend(
        [
            _element("a", [_text("Conocer más")], href="#contacto"),
            _element(
                "section",
                [
                    _element("h2", [_text("Una base lista para editar")]),
                    _element("p", [_text("Cambiá textos, colores y estructura desde el editor.")]),
                ],
                id="contacto",
            ),
        ]
    )
    return {
        "schemaVersion": "2.0",
        "settings": DOCUMENT_SETTINGS.copy(),
        "document": {
            "doctype": "html",
            "htmlAttributes": {"lang": "es", "dir": "ltr"},
            "head": {
                "title": title,
                "metas": [
                    {"charset": "UTF-8"},
                    {"name": "viewport", "content": "width=device-width, initial-scale=1"},
                ],
                "links": [],
                "scripts": [],
            },
            "body": {"attributes": {}, "children": [_element("main", body_children)]},
        },
        "styles": {
            "variables": {**preset["variables"], "--font-primary": "Inter, Arial, sans-serif"},
            "palette": {"id": preset["id"], "name": preset["name"], "source": "preset"},
            "rules": DEMO_RULES,
        },
        "components": {},
        "assets": assets,
    }


def _image_bytes(label: str, colors: tuple[str, str]) -> bytes:
    image = Image.new("RGB", (1200, 800), colors[0])
    draw = ImageDraw.Draw(image)
    draw.rectangle((720, 0, 1200, 800), fill=colors[1])
    draw.text((72, 72), label.upper(), fill="#ffffff")
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


class Command(BaseCommand):
    help = "Reset the local database and populate deterministic demo data."

    def handle(self, *args, **options):
        if not settings.DEBUG and os.environ.get("MOCKUP_ALLOW_NON_DEBUG") != "1":
            raise CommandError(
                "Refusing to reset a non-development database. "
                "Use config.settings.development or explicitly set "
                "MOCKUP_ALLOW_NON_DEBUG=1."
            )

        self.stdout.write(self.style.WARNING("Cleaning the database and media files..."))
        self._delete_stored_files()
        call_command("flush", interactive=False, verbosity=0)
        with transaction.atomic():
            seeded = self._seed()

        self.stdout.write(self.style.SUCCESS("Mockup data loaded successfully."))
        self.stdout.write(f"Login: {DEMO_USERNAME} / {DEMO_PASSWORD}")
        self.stdout.write(f"Published page: /t/{seeded['published'].public_slug}/")
        for label, model in seeded["models"]:
            self.stdout.write(f"{label}: {model.objects.count()}")

    def _delete_stored_files(self):
        for model, field_name in ((UploadedAsset, "file"), (Product, "digital_file")):
            for instance in model.objects.all().iterator():
                stored_file = getattr(instance, field_name)
                if stored_file.name:
                    stored_file.delete(save=False)

    def _seed(self) -> dict:
        User = get_user_model()
        demo = User.objects.create_user(
            username=DEMO_USERNAME,
            email=DEMO_EMAIL,
            password=DEMO_PASSWORD,
            first_name="Demo",
            last_name="Studio",
            is_staff=True,
            is_superuser=True,
        )
        ocean, forest, sunset = (_preset(name) for name in ("ocean", "forest", "sunset"))
        hero = self._create_asset(demo, "mockup-hero.png", "glow skin", ("#0f766e", "#14b8a6"))
        product_image = self._create_asset(
            demo, "mockup-product.png", "product", ("#c2410c", "#fb923c")
        )
        self._create_base_templates(ocean, sunset)

        published = UserTemplate.objects.create(
            owner=demo,
            name="GlowSkin — landing",
            description="Landing publicada para probar el flujo completo del editor.",
            accent=ocean["variables"]["--color-primary"],
            state=_page_state("Descubrí tu mejor rutina", ocean, hero.file.url),
        )
        published.publish()
        draft = UserTemplate.objects.create(
            owner=demo,
            name="Lanzamiento de otoño — borrador",
            description="Borrador no publicado para revisar el gallery del usuario.",
            accent=sunset["variables"]["--color-primary"],
            state=_page_state("Lanzamiento de otoño", sunset, product_image.file.url),
        )
        UserTemplateRevision.objects.bulk_create(
            [
                UserTemplateRevision(
                    user_template=draft, version=1, state=_page_state("Borrador inicial", sunset)
                ),
                UserTemplateRevision(user_template=draft, version=2, state=draft.state),
            ]
        )
        for name, palette in (
            ("Océano Demo", ocean),
            ("Bosque Demo", forest),
            ("Atardecer Demo", sunset),
        ):
            UserPalette.objects.create(
                owner=demo, slug=slugify(name), name=name, variables=palette["variables"]
            )
        project = Project.objects.create(
            owner=demo, name="GlowSkin / sitio público", state=published.state
        )
        ProjectRevision.objects.bulk_create(
            [
                ProjectRevision(
                    project=project,
                    version=1,
                    state=_page_state("GlowSkin — primera versión", ocean),
                    source=ProjectRevision.Source.MANUAL,
                    summary="Estructura inicial creada desde una plantilla.",
                    user=demo,
                ),
                ProjectRevision(
                    project=project,
                    version=2,
                    state=published.state,
                    source=ProjectRevision.Source.AI,
                    summary="Ajuste de copy y paleta con el asistente.",
                    user=demo,
                ),
            ]
        )
        download_product = Product.objects.create(
            owner=demo,
            name="Guía de rutina GlowSkin",
            description="PDF de ejemplo para probar productos y descargas digitales.",
            price_cents=2499,
            image=product_image,
        )
        download_product.digital_file.save(
            "mockup-guide.pdf", ContentFile(b"%PDF-1.4\n% mockup demo document\n"), save=True
        )
        Product.objects.create(
            owner=demo,
            name="Kit hidratación diaria",
            description="Producto físico de muestra con imagen y compra simulada.",
            price_cents=3999,
            image=hero,
        )
        Product.objects.create(
            owner=demo,
            name="Producto archivado",
            description="Producto inactivo para probar estados del catálogo.",
            price_cents=999,
            is_active=False,
        )
        PaymentGatewayConfig.objects.bulk_create(
            [
                PaymentGatewayConfig(
                    owner=demo, gateway=gateway, is_enabled=gateway in {"stripe", "mercadopago"}
                )
                for gateway in GATEWAY_CHOICES
            ]
        )
        Order.objects.bulk_create(
            [
                Order(
                    product=download_product,
                    gateway=Order.Gateway.STRIPE,
                    gateway_session_id="mockup_paid_001",
                    buyer_email="buyer@example.com",
                    amount_cents=download_product.price_cents,
                    currency=settings.DEFAULT_CURRENCY,
                    status=Order.Status.PAID,
                    download_token=Order.generate_download_token(),
                ),
                Order(
                    product=download_product,
                    gateway=Order.Gateway.MERCADOPAGO,
                    gateway_session_id="mockup_pending_001",
                    buyer_email="pending@example.com",
                    amount_cents=download_product.price_cents,
                    currency=settings.DEFAULT_CURRENCY,
                    status=Order.Status.PENDING,
                ),
                Order(
                    product=download_product,
                    gateway=Order.Gateway.STRIPE,
                    gateway_session_id="mockup_failed_001",
                    buyer_email="failed@example.com",
                    amount_cents=download_product.price_cents,
                    currency=settings.DEFAULT_CURRENCY,
                    status=Order.Status.FAILED,
                ),
            ]
        )
        self._create_analytics(published)
        models = [
            ("Users", User),
            ("Base templates", Template),
            ("User templates", UserTemplate),
            ("Projects", Project),
            ("Palettes", UserPalette),
            ("Assets", UploadedAsset),
            ("Products", Product),
            ("Gateway configs", PaymentGatewayConfig),
            ("Orders", Order),
            ("Analytics sessions", AnalyticsSession),
            ("Analytics events", AnalyticsEvent),
        ]
        return {"published": published, "models": models}

    def _create_base_templates(self, ocean: dict, sunset: dict):
        for slug, name, description, accent, order, state in (
            (
                "landing",
                "Landing (ejemplo)",
                "La landing de ejemplo completa, lista para personalizar.",
                ocean["variables"]["--color-primary"],
                0,
                None,
            ),
            (
                "blank",
                "En blanco",
                "Una página mínima con un título y un párrafo.",
                ocean["variables"]["--color-primary"],
                1,
                _page_state("Nueva página", ocean),
            ),
            (
                "coming-soon",
                "Próximamente",
                "Un hero centrado para una página de lanzamiento.",
                sunset["variables"]["--color-primary"],
                2,
                _page_state("Algo grande se viene", sunset),
            ),
        ):
            Template.objects.create(
                slug=slug,
                name=name,
                description=description,
                accent=accent,
                order=order,
                state=state,
            )

    def _create_asset(self, owner, filename: str, label: str, colors: tuple[str, str]):
        asset = UploadedAsset(owner=owner, width=1200, height=800, placeholder_color=colors[0])
        image = Image.new("RGB", (1200, 800), colors[0])
        draw = ImageDraw.Draw(image)
        draw.rectangle((720, 0, 1200, 800), fill=colors[1])
        draw.text((72, 72), label.upper(), fill="#ffffff")
        output = io.BytesIO()
        image.save(output, format="PNG")
        asset.file.save(filename, ContentFile(output.getvalue()), save=False)
        asset.save()
        return asset

    def _create_analytics(self, template):
        now = timezone.now()
        for index in range(3):
            started_at = now - timedelta(days=index, hours=index + 1)
            visitor = AnalyticsVisitor.objects.create(consented_at=started_at)
            session = AnalyticsSession.objects.create(
                visitor=visitor,
                template=template,
                last_seen=started_at + timedelta(minutes=8),
                entry_path="/",
                viewport_width=1440 if index == 0 else 390,
                viewport_height=900 if index == 0 else 844,
                duration_seconds=480 - index * 60,
                event_count=4,
            )
            AnalyticsVisitor.objects.filter(pk=visitor.pk).update(
                first_seen=started_at,
                last_seen=started_at + timedelta(minutes=8),
            )
            AnalyticsSession.objects.filter(pk=session.pk).update(
                started_at=started_at,
                ended_at=started_at + timedelta(minutes=8),
            )
            events = [
                AnalyticsEvent(session=session, kind=AnalyticsEvent.Kind.PAGEVIEW),
                AnalyticsEvent(
                    session=session,
                    kind=AnalyticsEvent.Kind.CLICK,
                    x="0.50",
                    y="0.42",
                    target="hero-cta",
                ),
                AnalyticsEvent(
                    session=session,
                    kind=AnalyticsEvent.Kind.MOVE,
                    x="0.62",
                    y="0.58",
                    target="hero",
                ),
                AnalyticsEvent(session=session, kind=AnalyticsEvent.Kind.CLICK, target="contacto"),
            ]
            AnalyticsEvent.objects.bulk_create(events)
