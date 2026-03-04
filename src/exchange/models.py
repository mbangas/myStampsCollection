"""Modelos da aplicação Trocas."""

from django.contrib.auth.models import User
from django.db import models

from catalog.models import Selo


class OfertaTroca(models.Model):
    """Selo que um utilizador disponibiliza para troca (tem repetidos)."""

    utilizador = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='ofertas_troca',
        verbose_name='Utilizador',
    )
    selo = models.ForeignKey(
        Selo,
        on_delete=models.PROTECT,
        related_name='ofertas',
        verbose_name='Selo',
    )
    quantidade_disponivel = models.PositiveSmallIntegerField(
        default=1,
        verbose_name='Quantidade Disponível',
    )
    ativa = models.BooleanField(default=True, verbose_name='Ativa')
    data_criacao = models.DateTimeField(auto_now_add=True, verbose_name='Data de Criação')

    class Meta:
        verbose_name = 'Oferta de Troca'
        verbose_name_plural = 'Ofertas de Troca'
        unique_together = [('utilizador', 'selo')]
        ordering = ['-data_criacao']

    def __str__(self) -> str:
        return f'{self.utilizador.username} oferece {self.selo}'


class PedidoTroca(models.Model):
    """Selo que um utilizador pretende obter via troca."""

    utilizador = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='pedidos_troca',
        verbose_name='Utilizador',
    )
    selo = models.ForeignKey(
        Selo,
        on_delete=models.PROTECT,
        related_name='pedidos',
        verbose_name='Selo',
    )
    quantidade_pretendida = models.PositiveSmallIntegerField(
        default=1,
        verbose_name='Quantidade Pretendida',
    )
    ativo = models.BooleanField(default=True, verbose_name='Ativo')
    data_criacao = models.DateTimeField(auto_now_add=True, verbose_name='Data de Criação')

    class Meta:
        verbose_name = 'Pedido de Troca'
        verbose_name_plural = 'Pedidos de Troca'
        unique_together = [('utilizador', 'selo')]
        ordering = ['-data_criacao']

    def __str__(self) -> str:
        return f'{self.utilizador.username} procura {self.selo}'


class Troca(models.Model):
    """Registo de uma troca entre dois utilizadores."""

    ESTADO_CHOICES = [
        ('pendente', 'Pendente'),
        ('aceite', 'Aceite'),
        ('concluida', 'Concluída'),
        ('recusada', 'Recusada'),
        ('cancelada', 'Cancelada'),
    ]

    iniciador = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='trocas_iniciadas',
        verbose_name='Iniciador',
    )
    receptor = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='trocas_recebidas',
        verbose_name='Recetor',
    )
    selos_oferecidos = models.ManyToManyField(
        Selo,
        related_name='trocas_como_oferta',
        verbose_name='Selos Oferecidos pelo Iniciador',
    )
    selos_pedidos = models.ManyToManyField(
        Selo,
        related_name='trocas_como_pedido',
        verbose_name='Selos Pedidos ao Recetor',
    )
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='pendente',
        verbose_name='Estado',
    )
    mensagem = models.TextField(blank=True, verbose_name='Mensagem')
    data_criacao = models.DateTimeField(auto_now_add=True, verbose_name='Data de Criação')
    data_atualizacao = models.DateTimeField(auto_now=True, verbose_name='Última Atualização')

    class Meta:
        verbose_name = 'Troca'
        verbose_name_plural = 'Trocas'
        ordering = ['-data_criacao']

    def __str__(self) -> str:
        return f'Troca #{self.pk}: {self.iniciador} ↔ {self.receptor} [{self.estado}]'
