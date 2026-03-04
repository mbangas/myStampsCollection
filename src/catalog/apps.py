"""Configuração da aplicação Catálogo."""

from django.apps import AppConfig


class CatalogConfig(AppConfig):
    """Configuração da app do catálogo de selos."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'catalog'
    verbose_name = 'Catálogo'
