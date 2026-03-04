"""Configuração da aplicação Contas."""

from django.apps import AppConfig


class AccountsConfig(AppConfig):
    """Configuração da app de gestão de utilizadores."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'
    verbose_name = 'Contas'
