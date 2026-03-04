"""Configuração do painel de administração para a Coleção."""

from django.contrib import admin

from .models import ItemColecao


@admin.register(ItemColecao)
class ItemColecaoAdmin(admin.ModelAdmin):
    """Admin dos itens da coleção."""

    list_display = (
        'utilizador', 'stamp', 'quantidade_possuida',
        'quantidade_repetidos', 'condicao', 'data_adicao',
    )
    list_filter = ('condicao', 'stamp__pais')
    search_fields = ('utilizador__username', 'stamp__titulo')
    readonly_fields = ('data_adicao', 'data_atualizacao')
