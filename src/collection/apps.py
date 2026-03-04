"""Configuração da aplicação Coleção."""

from django.apps import AppConfig


class CollectionConfig(AppConfig):
    """Configuração da app de gestão da coleção do utilizador."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'collection'
    verbose_name = 'Coleção'
