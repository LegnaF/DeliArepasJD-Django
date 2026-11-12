
"""
Django settings for deliarepas project.
Configuración de Deli Arepas JD.
"""

from pathlib import Path
import os


# =====================================================
# RUTAS DEL PROYECTO
# =====================================================

BASE_DIR = Path(__file__).resolve().parent.parent


# =====================================================
# SEGURIDAD
# =====================================================

SECRET_KEY = os.environ.get(
    'DJANGO_SECRET_KEY',
    'django-insecure-cambia-esta-clave-para-desarrollo'
)

DEBUG = True

ALLOWED_HOSTS = [
    'localhost',
    '127.0.0.1',
]


# =====================================================
# APLICACIONES INSTALADAS
# =====================================================

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'deliapp',
]


# =====================================================
# MIDDLEWARE
# =====================================================

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


# =====================================================
# CONFIGURACIÓN PRINCIPAL
# =====================================================

ROOT_URLCONF = 'deliarepas.urls'

WSGI_APPLICATION = 'deliarepas.wsgi.application'


# =====================================================
# PLANTILLAS HTML
# =====================================================

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]


# =====================================================
# BASE DE DATOS POSTGRESQL
# =====================================================

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'estadic',
        'USER': 'postgres',
        'PASSWORD': '123',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}


# =====================================================
# VALIDACIÓN DE CONTRASEÑAS
# =====================================================

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': (
            'django.contrib.auth.password_validation.'
            'UserAttributeSimilarityValidator'
        ),
    },
    {
        'NAME': (
            'django.contrib.auth.password_validation.'
            'MinimumLengthValidator'
        ),
    },
    {
        'NAME': (
            'django.contrib.auth.password_validation.'
            'CommonPasswordValidator'
        ),
    },
    {
        'NAME': (
            'django.contrib.auth.password_validation.'
            'NumericPasswordValidator'
        ),
    },
]


# =====================================================
# IDIOMA Y ZONA HORARIA
# =====================================================

LANGUAGE_CODE = 'es'

TIME_ZONE = 'America/Bogota'

USE_I18N = True

USE_TZ = True


# =====================================================
# ARCHIVOS ESTÁTICOS
# =====================================================

STATIC_URL = '/static/'

STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

STATIC_ROOT = BASE_DIR / 'staticfiles'


# =====================================================
# ARCHIVOS MULTIMEDIA
# =====================================================

MEDIA_URL = '/media/'

MEDIA_ROOT = BASE_DIR / 'media'


# =====================================================
# AUTENTICACIÓN
# =====================================================

LOGIN_URL = 'login'

LOGIN_REDIRECT_URL = 'inicio'

LOGOUT_REDIRECT_URL = 'inicio'


# =====================================================
# RECUPERACIÓN DE CONTRASEÑA
# =====================================================

# El enlace de recuperación dura 15 minutos.

PASSWORD_RESET_TIMEOUT = 900


# =====================================================
# CORREO ELECTRÓNICO REAL MEDIANTE GMAIL
# =====================================================

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'

EMAIL_HOST = 'smtp.gmail.com'

EMAIL_PORT = 587

EMAIL_USE_TLS = True

EMAIL_USE_SSL = False

EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '').strip()

EMAIL_HOST_PASSWORD = os.environ.get(
    'EMAIL_HOST_PASSWORD', ''
).replace(' ', '')

DEFAULT_FROM_EMAIL = EMAIL_HOST_USER or 'Deli Arepas JD'

EMAIL_SUBJECT_PREFIX = '[Deli Arepas JD] '

EMAIL_TIMEOUT = 20

SERVER_EMAIL = DEFAULT_FROM_EMAIL


# =====================================================
# CONFIGURACIÓN DE SESIONES
# =====================================================

SESSION_COOKIE_AGE = 86400

SESSION_SAVE_EVERY_REQUEST = True

SESSION_COOKIE_HTTPONLY = True

CSRF_COOKIE_HTTPONLY = False


# =====================================================
# CLAVE PRIMARIA PREDETERMINADA
# =====================================================

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
