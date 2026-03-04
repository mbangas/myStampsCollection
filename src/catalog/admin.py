"""Configuração do painel de administração para o Catálogo."""

from django.contrib import admin

from .models import Pais, Selo, Serie, Tema, Variante


@admin.register(Pais)
class PaisAdmin(admin.ModelAdmin):
    """Admin dos países."""

    list_display = ('nome', 'codigo_iso', 'total_selos')
    search_fields = ('nome', 'codigo_iso')
    ordering = ('nome',)


@admin.register(Tema)
class TemaAdmin(admin.ModelAdmin):
    """Admin dos temas dos selos."""

    list_display = ('nome',)
    search_fields = ('nome',)


@admin.register(Serie)
class SerieAdmin(admin.ModelAdmin):
    """Admin das séries / emissões de selos."""

    list_display = ('nome', 'pais', 'data_emissao', 'total_selos')
    list_filter = ('pais',)
    search_fields = ('nome',)
    ordering = ('pais', '-data_emissao')


@admin.register(Selo)
class SeloAdmin(admin.ModelAdmin):
    """Admin dos selos do catálogo."""

    list_display = ('titulo', 'pais', 'serie', 'ano', 'numero_catalogo', 'numero_mundifil', 'denominacao', 'moeda')
    list_filter = ('pais', 'serie', 'temas', 'ano')
    search_fields = ('titulo', 'numero_catalogo', 'numero_mundifil', 'descricao_tematica')
    filter_horizontal = ('temas',)
    readonly_fields = ('data_criacao', 'data_atualizacao')
    raw_id_fields = ('serie',)


@admin.register(Variante)
class VarianteAdmin(admin.ModelAdmin):
    """Admin das variantes de selos."""

    list_display = ('selo', 'codigo', 'descricao')
    search_fields = ('codigo', 'descricao', 'selo__titulo')
    list_filter = ('selo__pais',)
