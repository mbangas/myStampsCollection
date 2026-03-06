"""Modelos da aplicação Catálogo."""

from django.conf import settings
from django.db import models
from django.utils import timezone


def selo_imagem_upload_path(instance: 'Selo', filename: str) -> str:
    """Gera o caminho de upload organizado por país: stamps/<ISO>/<filename>."""
    codigo_iso = instance.pais.codigo_iso if instance.pais_id else 'OUTRO'
    return f'stamps/{codigo_iso}/{filename}'


class Pais(models.Model):
    """Representa um país emissor de selos."""

    nome = models.CharField(max_length=100, unique=True, verbose_name='Nome')
    codigo_iso = models.CharField(
        max_length=10,
        unique=True,
        verbose_name='Código ISO',
        help_text='Código ISO 3166-1 alpha-2/alpha-3, ou código customizado (ex.: PT-AZ).',
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


class Serie(models.Model):
    """Representa uma série / emissão (issue) de selos.

    Uma série agrupa os selos emitidos em conjunto numa determinada data,
    normalmente comemorando um evento ou tema comum.
    """

    pais = models.ForeignKey(
        Pais,
        on_delete=models.PROTECT,
        related_name='series',
        verbose_name='País',
    )
    nome = models.CharField(
        max_length=200,
        verbose_name='Nome da Série',
        help_text='Nome da emissão / issue (ex.: «Ceres», «Route of the Portuguese Cathedrals»).',
    )
    data_emissao = models.DateField(
        null=True,
        blank=True,
        verbose_name='Data de Emissão',
        help_text='Data em que a série foi emitida.',
    )

    class Meta:
        verbose_name = 'Série'
        verbose_name_plural = 'Séries'
        ordering = ['pais', '-data_emissao', 'nome']
        unique_together = [('pais', 'nome')]

    def __str__(self) -> str:
        if self.data_emissao:
            return f'{self.nome} ({self.data_emissao:%Y-%m-%d})'
        return self.nome

    @property
    def total_selos(self) -> int:
        """Devolve o número total de selos desta série."""
        return self.selos.count()


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
    serie = models.ForeignKey(
        Serie,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='selos',
        verbose_name='Série',
        help_text='Série / emissão a que o selo pertence.',
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
        upload_to=selo_imagem_upload_path,
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


class ImportacaoCatalogo(models.Model):
    """Regista o estado e o progresso de uma importação do StampData."""

    ESTADO_A_CORRER = 'a_correr'
    ESTADO_CONCLUIDO = 'concluido'
    ESTADO_ERRO = 'erro'

    ESTADO_CHOICES = [
        (ESTADO_A_CORRER, 'A correr'),
        (ESTADO_CONCLUIDO, 'Concluído'),
        (ESTADO_ERRO, 'Erro'),
    ]

    pais = models.ForeignKey(
        Pais,
        on_delete=models.CASCADE,
        related_name='importacoes',
        verbose_name='País',
    )
    issuer_id = models.IntegerField(verbose_name='StampData Issuer ID')
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default=ESTADO_A_CORRER,
        verbose_name='Estado',
    )
    fase_atual = models.CharField(max_length=300, blank=True, verbose_name='Fase atual')
    total_ids = models.IntegerField(default=0, verbose_name='Total de IDs encontrados')
    ids_processados = models.IntegerField(default=0, verbose_name='IDs processados (scrape)')
    selos_criados = models.IntegerField(default=0, verbose_name='Selos criados')
    selos_atualizados = models.IntegerField(default=0, verbose_name='Selos atualizados')
    erros_importacao = models.IntegerField(default=0, verbose_name='Erros de importação')
    imagens_total = models.IntegerField(default=0, verbose_name='Imagens a descarregar')
    imagens_processadas = models.IntegerField(default=0, verbose_name='Imagens processadas')
    mensagem_erro = models.TextField(blank=True, verbose_name='Mensagem de erro')
    iniciado_em = models.DateTimeField(auto_now_add=True, verbose_name='Iniciado em')
    concluido_em = models.DateTimeField(null=True, blank=True, verbose_name='Concluído em')
    iniciado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='importacoes_catalogo',
        verbose_name='Iniciado por',
    )

    class Meta:
        verbose_name = 'Importação de Catálogo'
        verbose_name_plural = 'Importações de Catálogo'
        ordering = ['-iniciado_em']

    def __str__(self) -> str:
        return f'Importação {self.pais.nome} (issuer={self.issuer_id}) – {self.get_estado_display()}'

    @property
    def progresso_pct(self) -> int:
        """Percentagem de progresso global (0–100)."""
        # Phase 1 (scrape): 0–60%, Phase 2 (images): 60–100%
        if self.total_ids == 0:
            return 0
        scrape_pct = min(self.ids_processados / self.total_ids, 1.0) * 60
        if self.imagens_total > 0:
            img_pct = min(self.imagens_processadas / self.imagens_total, 1.0) * 40
        else:
            img_pct = 40 if self.estado == self.ESTADO_CONCLUIDO else 0
        return int(scrape_pct + img_pct)

    def marcar_concluido(self) -> None:
        """Marca a importação como concluída."""
        self.estado = self.ESTADO_CONCLUIDO
        self.concluido_em = timezone.now()
        self.save(update_fields=['estado', 'concluido_em', 'fase_atual'])

    def marcar_erro(self, mensagem: str) -> None:
        """Marca a importação como falhada."""
        self.estado = self.ESTADO_ERRO
        self.concluido_em = timezone.now()
        self.mensagem_erro = mensagem[:2000]
        self.save(update_fields=['estado', 'concluido_em', 'mensagem_erro', 'fase_atual'])

