from django.db import migrations


def remove_blank(apps, schema_editor):
    Template = apps.get_model("editor", "Template")
    Template.objects.filter(slug="blank").delete()


def restore_blank(apps, schema_editor):
    Template = apps.get_model("editor", "Template")
    Template.objects.update_or_create(
        slug="blank",
        defaults={
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
    )


class Migration(migrations.Migration):
    dependencies = [("editor", "0004_usertemplaterevision")]
    operations = [migrations.RunPython(remove_blank, restore_blank)]
