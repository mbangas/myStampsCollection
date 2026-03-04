"""Configuração do painel de administração para as Trocas."""

from django.contrib import admin

from .models import OfertaTroca, PedidoTroca, Troca


@admin.register(OfertaTroca)
class OfertaTrocaAdmin(admin.ModelAdmin):
    """Admin das ofertas de troca."""

    list_display = ('utilizador', 'selo', 'quantidade_disponivel', 'ativa', 'data_criacao')
    list_filter = ('ativa', 'selo__pais')
    search_fields = ('utilizador__username', 'selo__titulo')


@admin.register(PedidoTroca)
class PedidoTrocaAdmin(admin.ModelAdmin):
    """Admin dos pedidos de troca."""

    list_display = ('utilizador', 'selo', 'quantidade_pretendida', 'ativo', 'data_criacao')
    list_filter = ('ativo', 'selo__pais')
    search_fields = ('utilizador__username', 'selo__titulo')


@admin.register(Troca)
class TrocaAdmin(admin.ModelAdmin):
    """Admin das trocas."""

    list_display = ('__str__', 'estado', 'data_criacao', 'data_atualizacao')
    list_filter = ('estado',)
    search_fields = ('iniciador__username', 'receptor__username')
    filter_horizontal = ('selos_oferecidos', 'selos_pedidos')
    readonly_fields = ('data_criacao', 'data_atualizacao')
