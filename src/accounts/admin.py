"""Configuração do painel de administração para Contas."""

from django.contrib import admin

from .models import PerfilUtilizador


@admin.register(PerfilUtilizador)
class PerfilUtilizadorAdmin(admin.ModelAdmin):
    """Admin do perfil do utilizador."""

    list_display = ('utilizador', 'data_registo', 'total_selos', 'total_repetidos')
    search_fields = ('utilizador__username', 'utilizador__email')
    filter_horizontal = ('paises_interesse',)
    readonly_fields = ('data_registo',)
