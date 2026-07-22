from django.db import migrations


def seed(apps, schema_editor):
    Template = apps.get_model("editor", "Template")
    templates = [
        {
            "slug": "landing",
            "name": "Landing (ejemplo)",
            "description": "La landing de ejemplo completa, lista para personalizar.",
            "accent": "#5b5ce2",
            "order": 0,
            "state": None,
        },
        {
            "slug": "blank",
            "name": "En blanco",
            "description": "Una página mínima con un título y un párrafo.",
            "accent": "#138a5b",
            "order": 1,
            "state": {
                "schemaVersion": "2.0",
                "settings": {
                    "strict": True,
                    "escapeText": True,
                    "allowRawHtml": False,
                    "allowInlineScripts": False,
                    "requireImageAlt": True,
                    "requireUniqueIds": True,
                },
                "document": {
                    "doctype": "html",
                    "htmlAttributes": {"lang": "es", "dir": "ltr"},
                    "head": {
                        "title": "Nueva página",
                        "metas": [
                            {"charset": "UTF-8"},
                            {"name": "viewport", "content": "width=device-width, initial-scale=1"},
                        ],
                        "links": [],
                        "scripts": [],
                    },
                    "body": {
                        "attributes": {"class": ["page"]},
                        "children": [
                            {
                                "type": "element",
                                "tag": "main",
                                "attributes": {"class": ["container"]},
                                "children": [
                                    {
                                        "type": "element",
                                        "tag": "h1",
                                        "attributes": {},
                                        "children": [{"type": "text", "value": "Tu título aquí"}],
                                    },
                                    {
                                        "type": "element",
                                        "tag": "p",
                                        "attributes": {},
                                        "children": [
                                            {"type": "text", "value": "Empieza a construir tu página."}
                                        ],
                                    },
                                ],
                            }
                        ],
                    },
                },
                "styles": {
                    "variables": {
                        "--color-primary": "#5b5ce2",
                        "--color-background": "#ffffff",
                        "--color-text": "#182034",
                        "--font-primary": "Inter, Arial, sans-serif",
                        "--max-width": "800px",
                    },
                    "rules": [
                        {"selector": "*", "declarations": {"box-sizing": "border-box"}},
                        {
                            "selector": "body",
                            "declarations": {
                                "margin": "0",
                                "color": "var(--color-text)",
                                "background": "var(--color-background)",
                                "font-family": "var(--font-primary)",
                                "line-height": "1.6",
                            },
                        },
                        {
                            "selector": ".container",
                            "declarations": {
                                "max-width": "var(--max-width)",
                                "margin": "0 auto",
                                "padding": "64px 24px",
                            },
                        },
                        {
                            "selector": "h1",
                            "declarations": {"font-size": "40px", "margin": "0 0 16px"},
                        },
                    ],
                },
            },
        },
        {
            "slug": "coming-soon",
            "name": "Próximamente",
            "description": "Un hero centrado a pantalla completa, fondo oscuro.",
            "accent": "#e2555e",
            "order": 2,
            "state": {
                "schemaVersion": "2.0",
                "settings": {
                    "strict": True,
                    "escapeText": True,
                    "allowRawHtml": False,
                    "allowInlineScripts": False,
                    "requireImageAlt": True,
                    "requireUniqueIds": True,
                },
                "document": {
                    "doctype": "html",
                    "htmlAttributes": {"lang": "es", "dir": "ltr"},
                    "head": {
                        "title": "Próximamente",
                        "metas": [
                            {"charset": "UTF-8"},
                            {"name": "viewport", "content": "width=device-width, initial-scale=1"},
                        ],
                        "links": [],
                        "scripts": [],
                    },
                    "body": {
                        "attributes": {"class": ["page"]},
                        "children": [
                            {
                                "type": "element",
                                "tag": "main",
                                "attributes": {"class": ["hero"]},
                                "children": [
                                    {
                                        "type": "element",
                                        "tag": "span",
                                        "attributes": {"class": ["eyebrow"]},
                                        "children": [{"type": "text", "value": "PRÓXIMAMENTE"}],
                                    },
                                    {
                                        "type": "element",
                                        "tag": "h1",
                                        "attributes": {},
                                        "children": [{"type": "text", "value": "Algo grande se viene"}],
                                    },
                                    {
                                        "type": "element",
                                        "tag": "p",
                                        "attributes": {},
                                        "children": [
                                            {
                                                "type": "text",
                                                "value": "Estamos trabajando en ello. Dejanos tu correo y te avisamos.",
                                            }
                                        ],
                                    },
                                    {
                                        "type": "element",
                                        "tag": "a",
                                        "attributes": {"class": ["button"], "href": "#"},
                                        "children": [{"type": "text", "value": "Avisame"}],
                                    },
                                ],
                            }
                        ],
                    },
                },
                "styles": {
                    "variables": {
                        "--color-primary": "#e2555e",
                        "--color-background": "#11172a",
                        "--color-text": "#f5f7ff",
                        "--font-primary": "Inter, Arial, sans-serif",
                    },
                    "rules": [
                        {"selector": "*", "declarations": {"box-sizing": "border-box"}},
                        {
                            "selector": "body",
                            "declarations": {
                                "margin": "0",
                                "color": "var(--color-text)",
                                "background": "var(--color-background)",
                                "font-family": "var(--font-primary)",
                            },
                        },
                        {
                            "selector": ".hero",
                            "declarations": {
                                "min-height": "100vh",
                                "display": "flex",
                                "flex-direction": "column",
                                "align-items": "center",
                                "justify-content": "center",
                                "text-align": "center",
                                "gap": "16px",
                                "padding": "24px",
                            },
                        },
                        {
                            "selector": ".eyebrow",
                            "declarations": {
                                "letter-spacing": "0.2em",
                                "font-size": "13px",
                                "color": "var(--color-primary)",
                                "font-weight": "700",
                            },
                        },
                        {
                            "selector": "h1",
                            "declarations": {"font-size": "clamp(32px, 6vw, 64px)", "margin": "0"},
                        },
                        {
                            "selector": "p",
                            "declarations": {"max-width": "460px", "opacity": "0.8", "margin": "0"},
                        },
                        {
                            "selector": ".button",
                            "declarations": {
                                "background": "var(--color-primary)",
                                "color": "#fff",
                                "padding": "12px 22px",
                                "border-radius": "10px",
                                "text-decoration": "none",
                                "font-weight": "700",
                                "margin-top": "8px",
                            },
                        },
                    ],
                },
            },
        },
    ]
    for t in templates:
        Template.objects.update_or_create(slug=t["slug"], defaults=t)


def unseed(apps, schema_editor):
    Template = apps.get_model("editor", "Template")
    Template.objects.filter(slug__in=["landing", "blank", "coming-soon"]).delete()


class Migration(migrations.Migration):
    dependencies = [("editor", "0001_initial")]
    operations = [migrations.RunPython(seed, unseed)]
