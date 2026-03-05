"""Vistas da aplicação Catálogo."""

import json
import threading

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import F, Q, Count, QuerySet
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.generic import DetailView, ListView


def _utilizador_e_admin(request: HttpRequest) -> bool:
    """Devolve True se o utilizador autenticado é administrador."""
    try:
        return bool(request.user.perfil.is_admin)
    except Exception:
        return False

from .models import ImportacaoCatalogo, Pais, Selo, Serie, Tema, Variante


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
        selos = self.object.selos.select_related('serie').prefetch_related('temas')

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

        # Ordenação: ano, data de emissão da série (sem série no fim), valor
        selos = selos.order_by(
            'ano',
            F('serie__data_emissao').asc(nulls_last=True),
            F('serie__nome').asc(nulls_last=True),
            'denominacao',
        )

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
        """Adiciona item de coleção, variantes e selos da mesma série ao contexto."""
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

        # Selos da mesma série (excluindo o atual)
        selos_serie: QuerySet = Selo.objects.none()
        if self.object.serie:
            selos_serie = (
                self.object.serie.selos
                .exclude(pk=self.object.pk)
                .order_by('denominacao')
            )

        context['item_colecao'] = item_colecao
        context['variantes'] = variantes
        context['variantes_possuidas_ids'] = variantes_possuidas_ids
        context['selos_serie'] = selos_serie

        # URL de retorno ao catálogo do país (enviada como parâmetro ?voltar=)
        voltar = self.request.GET.get('voltar', '').strip()
        if voltar and url_has_allowed_host_and_scheme(
            url=voltar,
            allowed_hosts={self.request.get_host()},
            require_https=self.request.is_secure(),
        ):
            context['back_url'] = voltar
        else:
            context['back_url'] = reverse('catalog:pais_detalhe', kwargs={'pk': self.object.pais.pk})
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


@login_required
def vista_criar_pais(request: HttpRequest) -> HttpResponse:
    """Cria um novo país/zona no catálogo via AJAX. Restrito ao administrador."""
    if not _utilizador_e_admin(request):
        return JsonResponse({'error': 'Acesso restrito ao administrador.'}, status=403)
    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido.'}, status=405)

    nome = request.POST.get('nome', '').strip()
    codigo_iso = request.POST.get('codigo_iso', '').strip().upper()
    descricao = request.POST.get('descricao', '').strip()

    if not nome or not codigo_iso:
        return JsonResponse(
            {'error': 'Nome e código ISO são obrigatórios.'},
            status=400,
        )

    # Se já existir um país com este código, devolver o URL
    existente = Pais.objects.filter(codigo_iso=codigo_iso).first()
    if existente:
        return JsonResponse({
            'exists': True,
            'url': reverse('catalog:pais_detalhe', kwargs={'pk': existente.pk}),
            'nome': existente.nome,
        })

    pais = Pais.objects.create(
        nome=nome,
        codigo_iso=codigo_iso,
        descricao=descricao,
    )
    return JsonResponse({
        'created': True,
        'url': reverse('catalog:pais_detalhe', kwargs={'pk': pais.pk}),
        'nome': pais.nome,
        'pk': pais.pk,
    })


@login_required
def vista_editar_descricao_pais(request: HttpRequest, pk: int) -> HttpResponse:
    """Atualiza a descrição de um país via AJAX."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido.'}, status=405)

    pais = get_object_or_404(Pais, pk=pk)
    descricao = request.POST.get('descricao', '').strip()
    pais.descricao = descricao
    pais.save(update_fields=['descricao'])
    return JsonResponse({'ok': True, 'descricao': pais.descricao})


@login_required
def vista_iniciar_importacao_stampdata(request: HttpRequest) -> JsonResponse:
    """Inicia uma importação do StampData em background. Restrito ao administrador."""
    if not _utilizador_e_admin(request):
        return JsonResponse({'error': 'Acesso restrito ao administrador.'}, status=403)
    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido.'}, status=405)

    pais_pk = request.POST.get('pais_pk', '').strip()
    issuer_id_raw = request.POST.get('issuer_id', '').strip()

    if not pais_pk or not issuer_id_raw:
        return JsonResponse({'error': 'pais_pk e issuer_id são obrigatórios.'}, status=400)

    try:
        issuer_id = int(issuer_id_raw)
        if issuer_id <= 0:
            raise ValueError
    except ValueError:
        return JsonResponse({'error': 'issuer_id deve ser um número inteiro positivo.'}, status=400)

    pais = get_object_or_404(Pais, pk=pais_pk)

    # Verificar se já existe uma importação em curso
    importacao_activa = ImportacaoCatalogo.objects.filter(
        estado=ImportacaoCatalogo.ESTADO_A_CORRER
    ).select_related('pais').first()

    if importacao_activa:
        return JsonResponse({
            'error': (
                f'Já está a decorrer uma importação para "{importacao_activa.pais.nome}". '
                'Aguarde que conclua antes de iniciar outra.'
            ),
            'importacao_id': importacao_activa.pk,
        }, status=409)

    # Criar registo de importação
    importacao = ImportacaoCatalogo.objects.create(
        pais=pais,
        issuer_id=issuer_id,
        estado=ImportacaoCatalogo.ESTADO_A_CORRER,
        fase_atual='A iniciar…',
        iniciado_por=request.user,
    )

    # Lançar thread em background
    from .importador_stampdata import executar_importacao  # importação local para evitar ciclos

    t = threading.Thread(
        target=executar_importacao,
        args=(importacao.pk,),
        daemon=True,
        name=f'importacao-{importacao.pk}',
    )
    t.start()

    return JsonResponse({
        'importacao_id': importacao.pk,
        'pais': pais.nome,
        'estado': importacao.estado,
    })


@login_required
def vista_estado_importacao(request: HttpRequest) -> JsonResponse:
    """Devolve o estado actual da importação em curso (ou da mais recente)."""
    importacao_id = request.GET.get('id')

    if importacao_id:
        try:
            importacao = ImportacaoCatalogo.objects.select_related('pais').get(
                pk=int(importacao_id)
            )
        except (ImportacaoCatalogo.DoesNotExist, ValueError):
            return JsonResponse({'error': 'Importação não encontrada.'}, status=404)
    else:
        # Devolve a importação activa ou a mais recente
        importacao = (
            ImportacaoCatalogo.objects.filter(estado=ImportacaoCatalogo.ESTADO_A_CORRER)
            .select_related('pais')
            .first()
            or ImportacaoCatalogo.objects.select_related('pais').first()
        )

    if not importacao:
        return JsonResponse({'nenhuma': True})

    return JsonResponse({
        'id': importacao.pk,
        'pais': importacao.pais.nome,
        'estado': importacao.estado,
        'fase_atual': importacao.fase_atual,
        'progresso_pct': importacao.progresso_pct,
        'total_ids': importacao.total_ids,
        'ids_processados': importacao.ids_processados,
        'selos_criados': importacao.selos_criados,
        'selos_atualizados': importacao.selos_atualizados,
        'erros': importacao.erros_importacao,
        'imagens_total': importacao.imagens_total,
        'imagens_processadas': importacao.imagens_processadas,
        'mensagem_erro': importacao.mensagem_erro,
        'iniciado_em': importacao.iniciado_em.isoformat() if importacao.iniciado_em else None,
        'concluido_em': importacao.concluido_em.isoformat() if importacao.concluido_em else None,
        'a_correr': importacao.estado == ImportacaoCatalogo.ESTADO_A_CORRER,
    })


@login_required
def vista_confirmar_apagar_pais(request: HttpRequest, pk: int) -> HttpResponse:
    """Confirmação e execução de remoção de um catálogo de país. Restrito ao administrador."""
    if not _utilizador_e_admin(request):
        messages.error(request, 'Acesso restrito ao administrador.')
        return redirect('catalog:catalogo')

    pais = get_object_or_404(Pais, pk=pk)

    if request.method == 'POST':
        nome = pais.nome
        with transaction.atomic():
            # Eliminar registos dependentes (todos com on_delete=PROTECT)
            from exchange.models import OfertaTroca, PedidoTroca
            from collection.models import ItemColecao

            selos_ids = list(pais.selos.values_list('pk', flat=True))
            OfertaTroca.objects.filter(selo_id__in=selos_ids).delete()
            PedidoTroca.objects.filter(selo_id__in=selos_ids).delete()
            ItemColecao.objects.filter(stamp_id__in=selos_ids).delete()
            pais.selos.all().delete()
            pais.series.all().delete()
            pais.delete()

        messages.success(request, f'Catálogo "{nome}" apagado com sucesso.')
        return redirect('catalog:catalogo')

    return render(request, 'catalog/confirmar_apagar_pais.html', {'pais': pais})
