"""Vistas da aplicação Catálogo."""

from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count
from django.shortcuts import get_object_or_404, render
from django.utils.decorators import method_decorator
from django.views.generic import DetailView, ListView

from .models import Pais, Selo, Tema


@method_decorator(login_required, name='dispatch')
class VistaCatalogo(ListView):
    """Lista todos os países disponíveis no catálogo."""

    template_name = 'catalog/catalogo.html'
    context_object_name = 'paises'

    def get_queryset(self):
        queryset = Pais.objects.annotate(num_selos=Count('selos'))
        paises_interesse = self.request.user.perfil.paises_interesse.values_list('id', flat=True)

        # Filtragem por pesquisa
        pesquisa = self.request.GET.get('q', '').strip()
        if pesquisa:
            queryset = queryset.filter(nome__icontains=pesquisa)

        return queryset.order_by('nome')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['pesquisa'] = self.request.GET.get('q', '')
        context['paises_interesse'] = (
            self.request.user.perfil.paises_interesse.values_list('id', flat=True)
        )
        context['temas'] = Tema.objects.all()
        return context


@method_decorator(login_required, name='dispatch')
class VistaPais(DetailView):
    """Detalhe de um país com a lista dos seus selos."""

    model = Pais
    template_name = 'catalog/pais_detalhe.html'
    context_object_name = 'pais'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        selos = self.object.selos.prefetch_related('temas')

        # Filtragem de selos
        pesquisa = self.request.GET.get('q', '').strip()
        tema_id = self.request.GET.get('tema', '').strip()
        ano = self.request.GET.get('ano', '').strip()

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

        # IDs dos selos que o utilizador já tem
        ids_colecao = set(
            self.request.user.itens_colecao
            .filter(stamp__pais=self.object)
            .values_list('stamp_id', flat=True)
        )

        context['selos'] = selos
        context['ids_colecao'] = ids_colecao
        context['temas'] = Tema.objects.all()
        context['anos'] = (
            self.object.selos.values_list('ano', flat=True)
            .distinct()
            .order_by('ano')
        )
        context['pesquisa'] = pesquisa
        context['tema_selecionado'] = tema_id
        context['ano_selecionado'] = ano
        return context


@method_decorator(login_required, name='dispatch')
class VistaSeloDetalhe(DetailView):
    """Detalhe completo de um selo do catálogo."""

    model = Selo
    template_name = 'catalog/selo_detalhe.html'
    context_object_name = 'selo'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Verifica se o utilizador tem este selo na coleção
        from collection.models import ItemColecao
        item_colecao = None
        try:
            item_colecao = self.request.user.itens_colecao.get(stamp=self.object)
        except ItemColecao.DoesNotExist:
            pass

        context['item_colecao'] = item_colecao
        return context
