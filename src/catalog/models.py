"""Modelos da aplicação Catálogo."""

from django.db import models


class Pais(models.Model):
    """Representa um país emissor de selos."""

    nome = models.CharField(max_length=100, unique=True, verbose_name='Nome')
    codigo_iso = models.CharField(
        max_length=3,
        unique=True,
        verbose_name='Código ISO',
        help_text='Código ISO 3166-1 alpha-2 ou alpha-3.',
    )
    bandeira = models.ImageField(
        upload_to='bandeiras/',
        blank=True,
        null=True,
        verbose_name='Bandeira',
    )
    descricao = models.TextField(blank=True, verbose_name='Descrição')

    class Meta:
        verbose_name = 'País'
        verbose_name_plural = 'Países'
        ordering = ['nome']

    def __str__(self) -> str:
        return self.nome

    @property
    def total_selos(self) -> int:
        """Devolve o número total de selos deste país no catálogo."""
        return self.selos.count()


class Tema(models.Model):
    """Representa uma temática de selos (ex.: fauna, flora, desporto)."""

    nome = models.CharField(max_length=100, unique=True, verbose_name='Nome')
    descricao = models.TextField(blank=True, verbose_name='Descrição')

    class Meta:
        verbose_name = 'Tema'
        verbose_name_plural = 'Temas'
        ordering = ['nome']

    def __str__(self) -> str:
        return self.nome


class Selo(models.Model):
    """Representa um selo no catálogo."""

    CONDICAO_CHOICES = [
        ('mint', 'Mint (perfeito)'),
        ('used', 'Usado'),
        ('cto', 'CTO (cancelado por encomenda)'),
        ('no_gum', 'Sem goma'),
        ('damaged', 'Com defeito'),
    ]

    pais = models.ForeignKey(
        Pais,
        on_delete=models.PROTECT,
        related_name='selos',
        verbose_name='País',
    )
    temas = models.ManyToManyField(
        Tema,
        blank=True,
        related_name='selos',
        verbose_name='Temas',
    )
    numero_catalogo = models.CharField(
        max_length=50,
        verbose_name='Número de Catálogo',
        help_text='Referência no catálogo Stanley Gibbons, Yvert, etc.',
    )
    titulo = models.CharField(max_length=200, verbose_name='Título')
    ano = models.PositiveSmallIntegerField(verbose_name='Ano de Emissão')
    denominacao = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='Denominação',
    )
    moeda = models.CharField(max_length=10, verbose_name='Moeda')
    descricao_tematica = models.TextField(
        verbose_name='Descrição Temática',
        help_text='Descreve o tema ou motivo representado no selo.',
    )
    descricao_tecnica = models.TextField(
        blank=True,
        verbose_name='Descrição Técnica',
        help_text='Dentado, formato, método de impressão, tiragem, etc.',
    )
    dentado = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Dentado',
        help_text='Ex.: 14 x 13½',
    )
    tiragem = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='Tiragem',
    )
    numero_mundifil = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Nº Mundifil',
        help_text='Referência no catálogo Mundifil.',
    )
    imagem = models.ImageField(
        upload_to='selos/',
        blank=True,
        null=True,
        verbose_name='Imagem',
    )
    data_criacao = models.DateTimeField(auto_now_add=True, verbose_name='Data de Criação')
    data_atualizacao = models.DateTimeField(auto_now=True, verbose_name='Última Atualização')

    class Meta:
        verbose_name = 'Selo'
        verbose_name_plural = 'Selos'
        ordering = ['pais', 'ano', 'numero_catalogo']
        unique_together = [('pais', 'numero_catalogo')]

    def __str__(self) -> str:
        return f'{self.pais.nome} – {self.titulo} ({self.ano})'


class Variante(models.Model):
    """Representa uma variante conhecida de um selo (ex.: cor, papel, dentado)."""

    selo = models.ForeignKey(
        Selo,
        on_delete=models.CASCADE,
        related_name='variantes',
        verbose_name='Selo',
    )
    codigo = models.CharField(max_length=50, verbose_name='Código / Designação')
    descricao = models.TextField(blank=True, verbose_name='Descrição')

    class Meta:
        verbose_name = 'Variante'
        verbose_name_plural = 'Variantes'
        ordering = ['codigo']

    def __str__(self) -> str:
        return f'{self.selo} – {self.codigo}'
