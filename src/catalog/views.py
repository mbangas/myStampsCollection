"""Vistas da aplicação Catálogo."""

import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Count, QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.views.generic import DetailView, ListView

from .models import Pais, Selo, Tema, Variante


@method_decorator(login_required, name='dispatch')
class VistaCatalogo(ListView):
    """Lista todos os países disponíveis no catálogo."""

    template_name = 'catalog/catalogo.html'
    context_object_name = 'paises'

    def get_queryset(self) -> QuerySet:
        """Devolve todos os países ordenados por nome, com contagem de selos."""
        queryset = Pais.objects.annotate(num_selos=Count('selos'))

        # Filtragem por pesquisa
        pesquisa = self.request.GET.get('q', '').strip()
        if pesquisa:
            queryset = queryset.filter(nome__icontains=pesquisa)

        return queryset.order_by('nome')

    def get_context_data(self, **kwargs) -> dict:
        """Adiciona temas, países de interesse e dados JSON do mapa ao contexto."""
        context = super().get_context_data(**kwargs)
        context['pesquisa'] = self.request.GET.get('q', '')
        context['paises_interesse'] = (
            self.request.user.perfil.paises_interesse.values_list('id', flat=True)
        )
        context['temas'] = Tema.objects.all()

        # JSON para o mapa D3 (todos os países, independente do filtro de pesquisa)
        todos_paises = Pais.objects.annotate(num_selos=Count('selos'))
        paises_map_data = [
            {
                'iso': p.codigo_iso,
                'nome': p.nome,
                'count': p.num_selos,
                'url': f'/catalogo/pais/{p.pk}/',
                'pk': p.pk,
            }
            for p in todos_paises
        ]
        context['paises_json'] = json.dumps(paises_map_data)
        return context


@method_decorator(login_required, name='dispatch')
class VistaPais(DetailView):
    """Detalhe de um país com a lista dos seus selos."""

    model = Pais
    template_name = 'catalog/pais_detalhe.html'
    context_object_name = 'pais'

    def get_context_data(self, **kwargs) -> dict:
        """Filtra selos por pesquisa, tema e ano; adiciona paginação e IDs da coleção."""
        context = super().get_context_data(**kwargs)
        selos = self.object.selos.prefetch_related('temas')

        # Lista de todos os anos disponíveis para este país (para a barra de navegação)
        anos_disponiveis = list(
            self.object.selos.values_list('ano', flat=True)
            .distinct()
            .order_by('ano')
        )

        # Filtragem de selos
        pesquisa = self.request.GET.get('q', '').strip()
        tema_id  = self.request.GET.get('tema', '').strip()
        ano      = self.request.GET.get('ano', '').strip()

        if pesquisa:
            selos = selos.filter(
                Q(titulo__icontains=pesquisa) |
                Q(descricao_tematica__icontains=pesquisa) |
                Q(numero_catalogo__icontains=pesquisa)
            )
        if tema_id:
            selos = selos.filter(temas__id=tema_id)
        if ano:
            selos = selos.filter(ano=ano)

        # Paginação: 24 selos por página
        paginator = Paginator(selos, 24)
        pagina_num = self.request.GET.get('pagina', 1)
        pagina = paginator.get_page(pagina_num)

        # IDs dos selos que o utilizador já tem
        ids_colecao = set(
            self.request.user.itens_colecao
            .filter(stamp__pais=self.object)
            .values_list('stamp_id', flat=True)
        )

        context['selos']              = pagina
        context['pagina']             = pagina
        context['ids_colecao']        = ids_colecao
        context['temas']              = Tema.objects.all()
        context['anos']               = anos_disponiveis
        context['pesquisa']           = pesquisa
        context['tema_selecionado']   = tema_id
        context['ano_selecionado']    = ano
        return context


@method_decorator(login_required, name='dispatch')
class VistaSeloDetalhe(DetailView):
    """Detalhe completo de um selo do catálogo."""

    model = Selo
    template_name = 'catalog/selo_detalhe.html'
    context_object_name = 'selo'

    def get_context_data(self, **kwargs) -> dict:
        """Adiciona item de coleção e variantes possuídas ao contexto do selo."""
        context = super().get_context_data(**kwargs)

        # Verifica se o utilizador tem este selo na coleção
        from collection.models import ItemColecao
        item_colecao = None
        try:
            item_colecao = self.request.user.itens_colecao.get(stamp=self.object)
        except ItemColecao.DoesNotExist:
            pass

        # Variantes conhecidas + quais o utilizador possui
        variantes = self.object.variantes.all()
        variantes_possuidas_ids = set()
        if item_colecao:
            variantes_possuidas_ids = set(
                item_colecao.variantes_possuidas.values_list('id', flat=True)
            )

        context['item_colecao'] = item_colecao
        context['variantes'] = variantes
        context['variantes_possuidas_ids'] = variantes_possuidas_ids
        return context


@login_required
def vista_upload_imagem_selo(request: HttpRequest, pk: int) -> HttpResponse:
    """Upload ou substituição de imagem de um selo do catálogo."""
    selo = get_object_or_404(Selo, pk=pk)

    if request.method == 'POST' and request.FILES.get('imagem'):
        # Remove imagem anterior se existir
        if selo.imagem:
            selo.imagem.delete(save=False)
        selo.imagem = request.FILES['imagem']
        selo.save(update_fields=['imagem'])
        messages.success(request, 'Imagem do selo atualizada com sucesso.')
    else:
        messages.error(request, 'Nenhuma imagem foi fornecida.')

    return redirect('catalog:selo_detalhe', pk=pk)
