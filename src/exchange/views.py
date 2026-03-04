"""Vistas da aplicação Trocas."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from collection.models import ItemColecao
from .models import OfertaTroca, PedidoTroca, Troca


@login_required
def vista_trocas(request):
    """Painel principal de trocas: ofertas, pedidos e histórico."""
    minhas_ofertas = OfertaTroca.objects.filter(
        utilizador=request.user, ativa=True
    ).select_related('selo__pais')

    meus_pedidos = PedidoTroca.objects.filter(
        utilizador=request.user, ativo=True
    ).select_related('selo__pais')

    trocas_ativas = Troca.objects.filter(
        Q(iniciador=request.user) | Q(receptor=request.user),
        estado__in=['pendente', 'aceite']
    ).select_related('iniciador', 'receptor').prefetch_related(
        'selos_oferecidos', 'selos_pedidos'
    )

    context = {
        'minhas_ofertas': minhas_ofertas,
        'meus_pedidos': meus_pedidos,
        'trocas_ativas': trocas_ativas,
    }
    return render(request, 'exchange/trocas.html', context)


@login_required
def vista_matches(request):
    """
    Mostra os matches automáticos: selos que o utilizador tem repetidos
    e que outros utilizadores procuram, e vice-versa.
    """
    # Selos que tenho repetidos
    meus_repetidos = (
        request.user.itens_colecao
        .filter(quantidade_repetidos__gt=0)
        .values_list('stamp_id', flat=True)
    )

    # Selos que não tenho mas procuro (tenho pedido ativo)
    meus_pedidos_ids = (
        request.user.pedidos_troca
        .filter(ativo=True)
        .values_list('selo_id', flat=True)
    )

    # Outros utilizadores que procuram selos que eu tenho repetidos
    # e que têm repetidos dos selos que eu procuro
    matches = []

    outros_utilizadores = User.objects.exclude(pk=request.user.pk)

    for outro in outros_utilizadores:
        # Selos que outro tem repetidos e eu quero
        selos_outros_repetidos = set(
            outro.itens_colecao.filter(quantidade_repetidos__gt=0)
            .values_list('stamp_id', flat=True)
        )
        selos_outros_pedidos = set(
            outro.pedidos_troca.filter(ativo=True)
            .values_list('selo_id', flat=True)
        )

        posso_dar = set(meus_repetidos) & selos_outros_pedidos
        posso_receber = selos_outros_repetidos & set(meus_pedidos_ids)

        if posso_dar or posso_receber:
            matches.append({
                'utilizador': outro,
                'posso_dar': posso_dar,
                'posso_receber': posso_receber,
                'score': len(posso_dar) + len(posso_receber),
            })

    # Ordena por relevância (mais matches primeiro)
    matches.sort(key=lambda m: m['score'], reverse=True)

    return render(request, 'exchange/matches.html', {'matches': matches})


@login_required
def propor_troca(request, utilizador_id: int):
    """Formula uma proposta de troca com outro utilizador."""
    receptor = get_object_or_404(User, pk=utilizador_id)

    if receptor == request.user:
        messages.error(request, 'Não podes propor uma troca contigo mesmo.')
        return redirect('exchange:matches')

    meus_repetidos = ItemColecao.objects.filter(
        utilizador=request.user, quantidade_repetidos__gt=0
    ).select_related('stamp__pais')

    repetidos_receptor = ItemColecao.objects.filter(
        utilizador=receptor, quantidade_repetidos__gt=0
    ).select_related('stamp__pais')

    if request.method == 'POST':
        selos_oferecer_ids = request.POST.getlist('selos_oferecer')
        selos_pedir_ids = request.POST.getlist('selos_pedir')
        mensagem = request.POST.get('mensagem', '')

        if not selos_oferecer_ids or not selos_pedir_ids:
            messages.error(request, 'Deves selecionar pelo menos um selo para oferecer e um para pedir.')
        else:
            troca = Troca.objects.create(
                iniciador=request.user,
                receptor=receptor,
                mensagem=mensagem,
            )
            troca.selos_oferecidos.set(selos_oferecer_ids)
            troca.selos_pedidos.set(selos_pedir_ids)
            messages.success(request, f'Proposta de troca enviada a {receptor.username}!')
            return redirect('exchange:trocas')

    context = {
        'receptor': receptor,
        'meus_repetidos': meus_repetidos,
        'repetidos_receptor': repetidos_receptor,
    }
    return render(request, 'exchange/propor_troca.html', context)


@login_required
def responder_troca(request, troca_id: int):
    """Aceita ou recusa uma proposta de troca."""
    troca = get_object_or_404(Troca, pk=troca_id, receptor=request.user, estado='pendente')

    if request.method == 'POST':
        acao = request.POST.get('acao')
        if acao == 'aceitar':
            troca.estado = 'aceite'
            troca.save()
            messages.success(request, 'Troca aceite! Entrem em contacto para combinar a entrega.')
        elif acao == 'recusar':
            troca.estado = 'recusada'
            troca.save()
            messages.info(request, 'Proposta de troca recusada.')
        return redirect('exchange:trocas')

    return render(request, 'exchange/responder_troca.html', {'troca': troca})


@login_required
def concluir_troca(request, troca_id: int):
    """Marca uma troca como concluída após a entrega física."""
    troca = get_object_or_404(
        Troca,
        pk=troca_id,
        estado='aceite'
    )

    if request.user not in (troca.iniciador, troca.receptor):
        messages.error(request, 'Não tens permissão para esta operação.')
        return redirect('exchange:trocas')

    if request.method == 'POST':
        troca.estado = 'concluida'
        troca.save()
        messages.success(request, 'Troca marcada como concluída! Não te esqueças de atualizar a tua coleção.')
        return redirect('exchange:trocas')

    return render(request, 'exchange/concluir_troca.html', {'troca': troca})


@login_required
def disponibilizar_repetidos(request):
    """
    Cria ou actualiza OfertaTroca para todos os itens da coleção do utilizador
    que tenham quantidade_repetidos > 0. Opera apenas via POST.
    """
    if request.method != 'POST':
        return redirect('exchange:trocas')

    itens_repetidos = ItemColecao.objects.filter(
        utilizador=request.user,
        quantidade_repetidos__gt=0,
    ).select_related('stamp')

    criadas = actualizadas = 0
    for item in itens_repetidos:
        oferta, criada = OfertaTroca.objects.update_or_create(
            utilizador=request.user,
            selo=item.stamp,
            defaults={
                'quantidade_disponivel': item.quantidade_repetidos,
                'ativa': True,
            },
        )
        if criada:
            criadas += 1
        else:
            actualizadas += 1

    total = criadas + actualizadas
    if total:
        messages.success(
            request,
            f'{total} oferta(s) de troca criadas/actualizadas '
            f'({criadas} nova(s), {actualizadas} actualizada(s)).'
        )
    else:
        messages.info(request, 'Não tens selos repetidos na coleção para disponibilizar.')

    return redirect('exchange:trocas')
