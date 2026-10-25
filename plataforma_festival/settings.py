"""
Configuración del Sistema Web de Votaciones · Festival de la Leyenda Vallenata 2027.

Los datos sensibles (clave secreta, usuario y contraseña de MySQL) NO se escriben
aquí: se leen del archivo .env que está al lado de manage.py (documento, 15.5).
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Lee las variables del archivo .env (si existe).
load_dotenv(BASE_DIR / ".env")


def env_bool(nombre, defecto=False):
    return os.environ.get(nombre, str(defecto)).strip().lower() in ("1", "true", "si", "sí", "yes")


SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
DEBUG = env_bool("DJANGO_DEBUG", False)
ALLOWED_HOSTS = [h.strip() for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",") if h.strip()]

if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "solo-para-desarrollo-cambiar-en-el-archivo-env"
    else:
        raise RuntimeError("Falta DJANGO_SECRET_KEY en el archivo .env")


# ---------------------------------------------------------------- aplicaciones
# Organización del código según la sección 15.4 del documento.
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    # Apps del proyecto
    "accounts",   # registro, autenticación y roles (CU-01, CU-02)
    "catalog",    # ediciones y categorías (CU-03, CU-06)
    "voting",     # votaciones, opciones y votos (CU-04, CU-07, CU-08)
    "results",    # resultados y panel (CU-05, CU-09)
    "audit",      # registro de auditoría (RF-16)
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "plataforma_festival.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],   # base.html y piezas compartidas
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

WSGI_APPLICATION = "plataforma_festival.wsgi.application"


# ---------------------------------------------------------------- base de datos
# MySQL (documento 15.3). Los valores vienen del archivo .env.
if os.environ.get("DB_ENGINE", "mysql") == "sqlite":
    # Solo para pruebas rápidas sin MySQL.
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": os.environ.get("DB_NAME", "festival_votaciones"),
            "USER": os.environ.get("DB_USER", "festival"),
            "PASSWORD": os.environ.get("DB_PASSWORD", ""),
            "HOST": os.environ.get("DB_HOST", "127.0.0.1"),
            "PORT": os.environ.get("DB_PORT", "3306"),
            "OPTIONS": {
                "charset": "utf8mb4",
                "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
            },
            "TEST": {"CHARSET": "utf8mb4", "COLLATION": "utf8mb4_unicode_ci"},
        }
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ---------------------------------------------------------------- usuarios
# Tabla "usuario" propia del modelo de datos (sección 11), con su rol.
AUTH_USER_MODEL = "accounts.Usuario"
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "catalog:categorias"

# RNF-02: contraseñas con hash seguro (PBKDF2 por defecto en Django).
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

SESSION_COOKIE_AGE = 60 * 60 * 8      # la sesión dura 8 horas
SESSION_COOKIE_HTTPONLY = True

# RNF-04 (preliminar*): intentos de inicio de sesión y votos por minuto.
LOGIN_MAX_INTENTOS = int(os.environ.get("LOGIN_MAX_INTENTOS", 5))
LOGIN_BLOQUEO_SEGUNDOS = int(os.environ.get("LOGIN_BLOQUEO_SEGUNDOS", 300))
VOTOS_MAX_POR_MINUTO = int(os.environ.get("VOTOS_MAX_POR_MINUTO", 10))


# ---------------------------------------------------------------- idioma y hora
LANGUAGE_CODE = "es-co"
TIME_ZONE = "America/Bogota"
USE_I18N = True
USE_TZ = True


# ---------------------------------------------------------------- archivos estáticos
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]   # CSS, JS e imágenes del prototipo
STATIC_ROOT = BASE_DIR / "staticfiles"     # destino de collectstatic al publicar


# ---------------------------------------------------------------- seguridad en producción
# RNF-01: HTTPS y cookies seguras cuando DEBUG está apagado.
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SSL_REDIRECT", True)
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "same-origin"


# ---------------------------------------------------------------- mensajes
# Los mensajes de Django usan las mismas clases del "toast" del prototipo.
from django.contrib.messages import constants as _mensajes  # noqa: E402

MESSAGE_TAGS = {
    _mensajes.SUCCESS: "ok",
    _mensajes.ERROR: "err",
    _mensajes.WARNING: "warn",
    _mensajes.INFO: "",
}
