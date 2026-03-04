"""Configuração da aplicação Trocas."""

from django.apps import AppConfig


class ExchangeConfig(AppConfig):
    """Configuração da app de trocas de selos entre utilizadores."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'exchange'
    verbose_name = 'Trocas'
