"""
Definições do Django para o projeto myStampsCollection.
"""

import sys
from pathlib import Path

from dotenv import load_dotenv
import os

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Adiciona a pasta src ao caminho de pesquisa de módulos Python
sys.path.insert(0, str(BASE_DIR / 'src'))

# Carrega variáveis de ambiente a partir do ficheiro .env
load_dotenv(BASE_DIR / '.env')

# ─── Segurança ────────────────────────────────────────────────────────────────

SECRET_KEY = os.getenv('SECRET_KEY', 'chave-insegura-apenas-para-desenvolvimento')

DEBUG = os.getenv('DEBUG', 'True') == 'True'

ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

# Origens de confiança para CSRF (necessário quando o Nginx faz proxy reverso)
_csrf_origins = os.getenv('CSRF_TRUSTED_ORIGINS', '')
CSRF_TRUSTED_ORIGINS = [o.strip() for o in _csrf_origins.split(',') if o.strip()]

# Suporte a proxy reverso (Nginx define X-Forwarded-For e X-Forwarded-Proto)
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# ─── Aplicações ───────────────────────────────────────────────────────────────

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    # Bibliotecas de terceiros
    'crispy_forms',
    'crispy_bootstrap5',
    # Aplicações do projeto
    'accounts',
    'catalog',
    'collection',
    'exchange',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'stamps_config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'src' / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'stamps_config.wsgi.application'

# ─── Base de Dados ────────────────────────────────────────────────────────────

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME', 'mystamps_db'),
        'USER': os.getenv('DB_USER', 'postgres'),
        'PASSWORD': os.getenv('DB_PASSWORD', 'password'),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
    }
}

# ─── Validação de Passwords ───────────────────────────────────────────────────

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# ─── Internacionalização ─────────────────────────────────────────────────────

LANGUAGE_CODE = 'pt-pt'

TIME_ZONE = 'Europe/Lisbon'

USE_I18N = True

USE_TZ = True

# ─── Ficheiros Estáticos ──────────────────────────────────────────────────────

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'css',
    BASE_DIR / 'src' / 'static',
]
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# ─── Ficheiros de Media (uploads) ─────────────────────────────────────────────

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# ─── Autenticação ─────────────────────────────────────────────────────────────

LOGIN_URL = '/contas/entrar/'
LOGIN_REDIRECT_URL = '/catalogo/'
LOGOUT_REDIRECT_URL = '/'

# ─── Crispy Forms ─────────────────────────────────────────────────────────────

CRISPY_ALLOWED_TEMPLATE_PACKS = 'bootstrap5'
CRISPY_TEMPLATE_PACK = 'bootstrap5'

# ─── Chave Primária Padrão ────────────────────────────────────────────────────

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
