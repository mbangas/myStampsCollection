"""Configuração do painel de administração para o Catálogo."""

from django.contrib import admin

from .models import ImportacaoCatalogo, Pais, Selo, Serie, Tema, Variante


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


@admin.register(ImportacaoCatalogo)
class ImportacaoCatalogoAdmin(admin.ModelAdmin):
    """Admin das importações de catálogo do StampData."""

    list_display = (
        'pais', 'issuer_id', 'estado', 'fase_atual',
        'selos_criados', 'selos_atualizados', 'iniciado_em', 'concluido_em',
    )
    list_filter = ('estado', 'pais')
    readonly_fields = (
        'pais', 'issuer_id', 'estado', 'fase_atual',
        'total_ids', 'ids_processados',
        'selos_criados', 'selos_atualizados', 'erros_importacao',
        'imagens_total', 'imagens_processadas',
        'mensagem_erro', 'iniciado_em', 'concluido_em', 'iniciado_por',
    )
    ordering = ('-iniciado_em',)
