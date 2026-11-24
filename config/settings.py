from datetime import timedelta
from pathlib import Path
import os

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
    DJANGO_TIME_ZONE=(str, "America/Sao_Paulo"),
    DJANGO_CSRF_TRUSTED_ORIGINS=(list, []),
    JWT_COOKIE_SAMESITE=(str, "Lax"),
    JWT_COOKIE_DOMAIN=(str, ""),
    POSTGRES_DB=(str, "finances"),
    POSTGRES_USER=(str, "finances"),
    POSTGRES_PASSWORD=(str, ""),
    POSTGRES_HOST=(str, "localhost"),
    POSTGRES_PORT=(int, 5432),
)
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY", default="")
DEBUG = env("DJANGO_DEBUG")
BOLSAI_API_KEY = env("BOLSAI_API_KEY", default="")
BRAPI_API_TOKEN = env("BRAPI_API_TOKEN", default="")
if not DEBUG and not SECRET_KEY:
    raise environ.ImproperlyConfigured("DJANGO_SECRET_KEY deve ser definido fora do modo debug.")

ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS")
LOCAL_DEVELOPMENT_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS",
    default=LOCAL_DEVELOPMENT_ORIGINS if DEBUG else [],
)
CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[]) or CORS_ALLOWED_ORIGINS
CSRF_COOKIE_SAMESITE = env("JWT_COOKIE_SAMESITE")
CORS_ALLOW_CREDENTIALS = True
TIME_ZONE = env("DJANGO_TIME_ZONE")
LANGUAGE_CODE = "pt-br"
USE_I18N = True
USE_TZ = True

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "django_filters",
    "drf_spectacular",
    "core",
    
    
    "apps.authentication",
    "apps.users",
    "apps.transactions",
    "apps.loans",
    "apps.debtors",
    "apps.monthlies",
    "apps.wishlist",
    "apps.investments",
    "apps.notifications",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
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

DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL:
    DATABASES = {
        "default": env.db("DATABASE_URL")
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("POSTGRES_DB"),
            "USER": env("POSTGRES_USER"),
            "PASSWORD": env("POSTGRES_PASSWORD"),
            "HOST": env("POSTGRES_HOST"),
            "PORT": env("POSTGRES_PORT"),
            "CONN_MAX_AGE": 60,
            "OPTIONS": {"connect_timeout": 5},
        }
    }


DATABASES["default"]["CONN_MAX_AGE"] = 0


AUTH_USER_MODEL = "users.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

REST_FRAMEWORK = {
    "EXCEPTION_HANDLER": "core.exception_handler.rendvest_exception_handler",
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.authentication.authentication.CookieJWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 5,
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.ScopedRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "auth_register": "5/hour",
        "contact_message": "5/hour",
        "auth_login": "5/minute",
        "auth_refresh": "30/minute",
        "auth_logout": "10/minute",
        "investment_research": "60/minute",
        "fund_refresh": "6/hour",
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
}

JWT_COOKIE_ACCESS_NAME = "access_token"
JWT_COOKIE_REFRESH_NAME = "refresh_token"
JWT_COOKIE_ACCESS_PATH = "/api/v1/"
JWT_COOKIE_REFRESH_PATH = "/api/v1/auth/"
JWT_COOKIE_SECURE = env.bool("JWT_COOKIE_SECURE", default=not DEBUG)
JWT_COOKIE_SAMESITE = env("JWT_COOKIE_SAMESITE")
JWT_COOKIE_DOMAIN = env("JWT_COOKIE_DOMAIN") or None

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SECURE_SSL_REDIRECT = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=not DEBUG)
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_HSTS_SECONDS = env.int("DJANGO_SECURE_HSTS_SECONDS", default=0)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool(
    "DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS",
    default=False,
)

SPECTACULAR_SETTINGS = {
    "TITLE": "Rendvest API",
    "DESCRIPTION": "API para gerenciamento de ganhos e gastos.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
