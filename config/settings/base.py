"""Base settings shared by every environment."""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
    CSRF_TRUSTED_ORIGINS=(list, ["http://localhost:8000"]),
    CORS_ALLOWED_ORIGINS=(list, ["http://localhost:8000"]),
    AI_REQUEST_TIMEOUT=(int, 30),
    AI_MAX_OPERATIONS=(int, 50),
    AI_MAX_INPUT_CHARACTERS=(int, 30000),
    # Generous enough for a full generated page document (reasoning + JSON) —
    # too low and the model gets cut off mid-JSON, producing invalid output.
    AI_MAX_OUTPUT_TOKENS=(int, 32000),
    AI_MODEL=(str, "gpt-4o-mini"),
    OPENAI_API_KEY=(str, ""),
    OPENCODE_ZEN_API_KEY=(str, ""),
    OPENCODE_ZEN_MODEL=(str, "minimax-m3"),
    # Used for conversational wizard calls (dynamic questions, review/
    # clarification) — the heavy structured full-document generation stays
    # on OPENCODE_ZEN_MODEL, which has proven more reliable at that specific
    # large-JSON task. See WizardAIService.
    OPENCODE_ZEN_CHAT_MODEL=(str, "mimo-v2.5"),
    OPENCODE_ZEN_BASE_URL=(str, "https://opencode.ai/zen/go/v1"),
    DEFAULT_CURRENCY=(str, "usd"),
    ANALYTICS_RETENTION_DAYS=(int, 90),
    ANALYTICS_COOKIE_MAX_AGE=(int, 60 * 60 * 24 * 365),
    # Console backend prints to stdout — safe, no external dependency,
    # works offline. Same swappable-provider shape as AI_PROVIDER: set
    # EMAIL_BACKEND to "django.core.mail.backends.smtp.EmailBackend" (with
    # EMAIL_HOST/PORT/USE_TLS/HOST_USER/HOST_PASSWORD) for a real deploy.
    EMAIL_BACKEND=(str, "django.core.mail.backends.console.EmailBackend"),
    DEFAULT_FROM_EMAIL=(str, "noreply@example.com"),
    EMAIL_HOST=(str, ""),
    EMAIL_PORT=(int, 587),
    EMAIL_USE_TLS=(bool, True),
    EMAIL_HOST_USER=(str, ""),
    EMAIL_HOST_PASSWORD=(str, ""),
    HOTMART_AUTH_BASE_URL=(str, "https://api-sec-vlc.hotmart.com/security/oauth"),
    HOTMART_API_BASE_URL=(str, "https://developers.hotmart.com/products/api/v1"),
    HOTMART_REQUEST_TIMEOUT=(int, 10),
)

# Read .env when present (development). In production, real env vars win.
env_file = BASE_DIR / ".env"
if env_file.exists():
    environ.Env.read_env(str(env_file))

SECRET_KEY = env("DJANGO_SECRET_KEY", default="insecure-dev-key-change-me")
DEBUG = env("DJANGO_DEBUG")
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "apps.accounts",
    "apps.editor",
    "apps.ai_assistant",
    "apps.projects",
    "apps.storefront",
    "apps.analytics",
    "apps.hotmart",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "config.middleware.ContentSecurityPolicyMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": env.db("DATABASE_URL", default="sqlite:///" + str(BASE_DIR / "db.sqlite3")),
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "es"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# User-uploaded wizard images (apps/editor/models.py's UploadedAsset). Served
# by config/urls.py's own route (ponytail: plain Django file serving, fine at
# this app's scale — swap for object storage/CDN if upload volume ever grows).
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "editor:editor"
LOGOUT_REDIRECT_URL = "accounts:login"

# --- Django REST Framework ------------------------------------------------
# The editor is same-origin behind login, so the browser's session cookie (with
# CSRF) authenticates API calls. No token/device flow needed.
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ("rest_framework.authentication.SessionAuthentication",),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_THROTTLE_CLASSES": ("rest_framework.throttling.ScopedRateThrottle",),
    "DEFAULT_THROTTLE_RATES": {
        "ai_transform": "20/m",
        "ai_wizard_questions": "10/m",
        "ai_wizard_review": "15/m",
        "ai_wizard_generate": "6/m",
        "html_import": "20/m",
        "wizard_upload": "20/m",
        "public_template_view": "60/m",
        "checkout_session_create": "10/m",
        "digital_download": "20/m",
        "analytics_consent": "10/m",
        "analytics_collect": "120/m",
    },
}

# --- CORS -----------------------------------------------------------------
CORS_ALLOWED_ORIGINS = env("CORS_ALLOWED_ORIGINS")
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = env("CSRF_TRUSTED_ORIGINS")

# --- AI assistant ---------------------------------------------------------
OPENAI_API_KEY = env("OPENAI_API_KEY")
AI_MODEL = env("AI_MODEL")
AI_REQUEST_TIMEOUT = env("AI_REQUEST_TIMEOUT")
AI_MAX_OPERATIONS = env("AI_MAX_OPERATIONS")
AI_MAX_INPUT_CHARACTERS = env("AI_MAX_INPUT_CHARACTERS")
AI_MAX_OUTPUT_TOKENS = env("AI_MAX_OUTPUT_TOKENS")
OPENCODE_ZEN_API_KEY = env("OPENCODE_ZEN_API_KEY")
OPENCODE_ZEN_MODEL = env("OPENCODE_ZEN_MODEL")
OPENCODE_ZEN_CHAT_MODEL = env("OPENCODE_ZEN_CHAT_MODEL")
OPENCODE_ZEN_BASE_URL = env("OPENCODE_ZEN_BASE_URL")
# Provider is swappable; fake provider needs no API key (tests, local dev).
AI_PROVIDER = env("AI_PROVIDER", default="openai" if OPENAI_API_KEY else "fake")

# --- Storefront / payments --------------------------------------------------
# Per-gateway credentials are owner-configured via /config (PaymentGatewayConfig,
# encrypted at rest — see apps/storefront/crypto.py) rather than env vars: this
# is a multi-tenant editor where each seller has their own Stripe/Mercado
# Pago/etc account, not one global gateway for the whole deployment. Only
EMAIL_BACKEND = env("EMAIL_BACKEND")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL")
EMAIL_HOST = env("EMAIL_HOST")
EMAIL_PORT = env("EMAIL_PORT")
EMAIL_USE_TLS = env("EMAIL_USE_TLS")
EMAIL_HOST_USER = env("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD")

# DEFAULT_CURRENCY stays a deployment-wide setting (not a secret, not
# per-gateway).
DEFAULT_CURRENCY = env("DEFAULT_CURRENCY")

# Anonymous analytics is opt-in and bounded by the retention command. The
# visitor cookie is pseudonymous and intentionally separate from auth.session.
ANALYTICS_RETENTION_DAYS = env("ANALYTICS_RETENTION_DAYS")
ANALYTICS_COOKIE_MAX_AGE = env("ANALYTICS_COOKIE_MAX_AGE")

# --- Hotmart integration ----------------------------------------------------
# No platform-level credentials: each seller pastes her own Developer
# Credentials (client_credentials grant), stored encrypted on
# HotmartConnection — see apps/hotmart/models.py and views.CredentialsView.
# Only the shared API/auth base URLs and timeout remain platform-level
# config. Without a connection's own client id and secret,
# build_hotmart_client() always returns the fake client.
HOTMART_AUTH_BASE_URL = env("HOTMART_AUTH_BASE_URL")
HOTMART_API_BASE_URL = env("HOTMART_API_BASE_URL")
HOTMART_REQUEST_TIMEOUT = env("HOTMART_REQUEST_TIMEOUT")

# --- Security headers ------------------------------------------------------
DATA_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024  # 1 MB request body cap
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "SAMEORIGIN"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
