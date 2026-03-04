"""Modelos da aplicação Coleção."""

from django.contrib.auth.models import User
from django.db import models

from catalog.models import Selo


class ItemColecao(models.Model):
    """Registo de um selo na coleção de um utilizador."""

    CONDICAO_CHOICES = [
        ('mint', 'Mint (perfeito)'),
        ('used', 'Usado'),
        ('cto', 'CTO (cancelado por encomenda)'),
        ('no_gum', 'Sem goma'),
        ('damaged', 'Com defeito'),
    ]

    utilizador = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='itens_colecao',
        verbose_name='Utilizador',
    )
    stamp = models.ForeignKey(
        Selo,
        on_delete=models.PROTECT,
        related_name='itens_colecao',
        verbose_name='Selo',
    )
    quantidade_possuida = models.PositiveSmallIntegerField(
        default=1,
        verbose_name='Quantidade Possuída',
    )
    quantidade_repetidos = models.PositiveSmallIntegerField(
        default=0,
        verbose_name='Repetidos (disponíveis para troca)',
    )
    condicao = models.CharField(
        max_length=20,
        choices=CONDICAO_CHOICES,
        default='mint',
        verbose_name='Condição',
    )
    notas = models.TextField(blank=True, verbose_name='Notas pessoais')
    data_adicao = models.DateTimeField(auto_now_add=True, verbose_name='Data de Adição')
    data_atualizacao = models.DateTimeField(auto_now=True, verbose_name='Última Atualização')

    class Meta:
        verbose_name = 'Item da Coleção'
        verbose_name_plural = 'Itens da Coleção'
        unique_together = [('utilizador', 'stamp')]
        ordering = ['stamp__pais__nome', 'stamp__ano']

    def __str__(self) -> str:
        return f'{self.utilizador.username} – {self.stamp}'

    def clean(self):
        """Valida que repetidos não excede o total possuído."""
        from django.core.exceptions import ValidationError
        if self.quantidade_repetidos > self.quantidade_possuida:
            raise ValidationError(
                'Os repetidos não podem exceder a quantidade total possuída.'
            )
