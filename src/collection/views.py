"""Vistas da aplicação Coleção."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Sum, Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from catalog.models import Pais, Selo
from .forms import FormularioItemColecao, FormularioLocalizacaoBulk
from .models import ItemColecao


@login_required
def vista_colecao(request):
    """Mostra a coleção completa do utilizador com indicadores."""
    itens = (
        request.user.itens_colecao
        .select_related('stamp__pais')
        .prefetch_related('stamp__temas')
        .order_by('stamp__pais__nome', 'stamp__ano')
    )

    # Filtros
    pais_id = request.GET.get('pais', '').strip()
    pesquisa = request.GET.get('q', '').strip()

    if pais_id:
        itens = itens.filter(stamp__pais_id=pais_id)
    if pesquisa:
        itens = itens.filter(stamp__titulo__icontains=pesquisa)

    # Indicadores
    totais = request.user.itens_colecao.aggregate(
        total_selos=Sum('quantidade_possuida'),
        total_repetidos=Sum('quantidade_repetidos'),
        paises_distintos=Count('stamp__pais', distinct=True),
        titulos_distintos=Count('stamp', distinct=True),
    )

    paises = Pais.objects.filter(
        selos__itens_colecao__utilizador=request.user
    ).distinct().order_by('nome')

    # Paginação: 25 itens por página
    paginator = Paginator(itens, 25)
    pagina_num = request.GET.get('pagina', 1)
    pagina = paginator.get_page(pagina_num)

    context = {
        'itens': pagina,
        'pagina': pagina,
        'totais': totais,
        'paises': paises,
        'pais_selecionado': pais_id,
        'pesquisa': pesquisa,
    }
    return render(request, 'collection/colecao.html', context)


@login_required
def adicionar_selo(request, selo_id: int):
    """Adiciona um selo à coleção ou redireciona para edição se já existir."""
    selo = get_object_or_404(Selo, pk=selo_id)

    item_existente = request.user.itens_colecao.filter(stamp=selo).first()
    if item_existente:
        messages.info(request, 'Este selo já está na tua coleção. Podes editar a quantidade.')
        return redirect('collection:editar_item', pk=item_existente.pk)

    if request.method == 'POST':
        formulario = FormularioItemColecao(request.POST, selo=selo)
        if formulario.is_valid():
            item = formulario.save(commit=False)
            item.utilizador = request.user
            item.stamp = selo
            item.save()
            formulario.save_m2m()
            messages.success(request, f'"{selo.titulo}" adicionado à tua coleção!')
            return redirect('collection:colecao')
    else:
        formulario = FormularioItemColecao(selo=selo)

    return render(request, 'collection/formulario_item.html', {
        'formulario': formulario,
        'selo': selo,
        'acao': 'Adicionar',
    })


@login_required
def editar_item(request, pk: int):
    """Edita a quantidade e condição de um item da coleção."""
    item = get_object_or_404(ItemColecao, pk=pk, utilizador=request.user)

    if request.method == 'POST':
        formulario = FormularioItemColecao(request.POST, instance=item, selo=item.stamp)
        if formulario.is_valid():
            formulario.save()
            messages.success(request, 'Coleção atualizada com sucesso.')
            return redirect('collection:colecao')
    else:
        formulario = FormularioItemColecao(instance=item, selo=item.stamp)

    return render(request, 'collection/formulario_item.html', {
        'formulario': formulario,
        'selo': item.stamp,
        'acao': 'Editar',
    })


@login_required
def remover_item(request, pk: int):
    """Remove um item da coleção do utilizador."""
    item = get_object_or_404(ItemColecao, pk=pk, utilizador=request.user)

    if request.method == 'POST':
        titulo = item.stamp.titulo
        item.delete()
        messages.success(request, f'"{titulo}" removido da tua coleção.')
        return redirect('collection:colecao')

    return render(request, 'collection/confirmar_remocao.html', {'item': item})


@login_required
def atualizar_localizacao_bulk(request):
    """Atualiza a localização de múltiplos itens da coleção de uma vez."""
    if request.method == 'POST':
        formulario = FormularioLocalizacaoBulk(request.POST)
        if formulario.is_valid():
            localizacao = formulario.cleaned_data['localizacao']
            ids_raw = formulario.cleaned_data['itens']
            try:
                ids = [int(i) for i in ids_raw.split(',') if i.strip().isdigit()]
            except ValueError:
                ids = []

            if ids:
                atualizados = (
                    request.user.itens_colecao
                    .filter(pk__in=ids)
                    .update(localizacao=localizacao)
                )
                messages.success(
                    request,
                    f'Localização "{localizacao}" aplicada a {atualizados} selos.'
                )
            else:
                messages.warning(request, 'Nenhum selo selecionado.')
        else:
            messages.error(request, 'Formulário inválido.')

    return redirect('collection:colecao')

