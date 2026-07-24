from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SHARED_TOKEN_LINK = "{% static 'shared/tokens.css' %}"
TOKEN_PAGES = (
    "templates/editor/editor.html",
    "templates/editor/template_wizard.html",
    "templates/editor/home.html",
    "templates/editor/gallery.html",
    "templates/storefront/products.html",
    "templates/storefront/payment_config.html",
    "templates/storefront/success.html",
    "templates/storefront/checkout_cancel.html",
    "templates/registration/login.html",
    "templates/registration/signup.html",
)


def read_project_file(path):
    return (PROJECT_ROOT / path).read_text()


def test_server_rendered_surfaces_link_shared_design_tokens():
    for path in TOKEN_PAGES:
        assert SHARED_TOKEN_LINK in read_project_file(path), path


def test_server_rendered_surfaces_do_not_redeclare_page_token_palettes():
    for path in TOKEN_PAGES:
        source = read_project_file(path)
        assert ":root" not in source, path
        assert "var(--bg)" not in source, path
        assert "var(--surface)" not in source, path
        assert "var(--text-muted)" not in source, path


def test_shared_token_file_owns_the_canonical_palette():
    source = read_project_file("static/shared/tokens.css")

    for token in (
        "--app-bg",
        "--panel-bg",
        "--border",
        "--text",
        "--muted",
        "--primary",
        "--font-sans",
        "--radius",
        "--shadow",
    ):
        assert token in source
