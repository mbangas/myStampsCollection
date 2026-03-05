"""Geração de PDF com a lista de selos em falta por país."""

from io import BytesIO
from itertools import groupby
from pathlib import Path
from typing import Any

from django.conf import settings
from django.contrib.auth.models import User
from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from catalog.models import Pais, Selo


# ── Estilos ──────────────────────────────────────────────────────────────────

_BASE_STYLES = getSampleStyleSheet()

STYLE_TITLE = ParagraphStyle(
    'FaltasTitulo',
    parent=_BASE_STYLES['Heading1'],
    fontSize=14,
    textColor=colors.HexColor('#1a5cb0'),
    spaceAfter=2 * mm,
)

STYLE_SUBTITLE = ParagraphStyle(
    'FaltasSubtitulo',
    parent=_BASE_STYLES['Normal'],
    fontSize=8,
    textColor=colors.HexColor('#666666'),
    spaceAfter=4 * mm,
)

STYLE_SERIE = ParagraphStyle(
    'FaltasSerie',
    parent=_BASE_STYLES['Heading3'],
    fontSize=7.5,
    textColor=colors.HexColor('#1a5cb0'),
    spaceBefore=3 * mm,
    spaceAfter=1 * mm,
)

STYLE_CELL = ParagraphStyle(
    'FaltasCell',
    parent=_BASE_STYLES['Normal'],
    fontSize=6,
    leading=7.5,
    textColor=colors.HexColor('#222222'),
)

STYLE_CELL_HEADER = ParagraphStyle(
    'FaltasCellHeader',
    parent=STYLE_CELL,
    fontSize=6,
    textColor=colors.HexColor('#555555'),
    leading=7.5,
)

# Dimensões de página
PAGE_W, PAGE_H = A4
MARGIN = 12 * mm
CONTENT_W = PAGE_W - 2 * MARGIN

# Placeholder fixo para thumbnail
THUMB_W = 9 * mm
THUMB_H = 12 * mm

# Altura fixa de cada linha (placeholder uniforme)
ROW_H = THUMB_H + 1.5 * mm


# ── Helpers ──────────────────────────────────────────────────────────────────


def _resolve_image_path(selo: Selo) -> str | None:
    """Devolve o caminho absoluto da imagem do selo, ou None."""
    if not selo.imagem:
        return None
    caminho = Path(settings.MEDIA_ROOT) / str(selo.imagem)
    if caminho.exists():
        return str(caminho)
    return None


def _make_thumb(caminho: str | None) -> Image | str:
    """Cria thumbnail que cabe no placeholder mantendo o rácio da imagem."""
    if caminho is None:
        return ''
    try:
        pil_img = PILImage.open(caminho)
        pil_img.thumbnail((48, 64), PILImage.LANCZOS)
        buf = BytesIO()
        fmt = 'JPEG'
        if pil_img.mode in ('RGBA', 'P', 'LA'):
            fmt = 'PNG'
        elif pil_img.mode != 'RGB':
            pil_img = pil_img.convert('RGB')
        pil_img.save(buf, format=fmt, quality=45, optimize=True)
        buf.seek(0)

        # Calcular dimensões que cabem no placeholder mantendo o rácio
        orig_w, orig_h = pil_img.size
        ratio = min(THUMB_W / orig_w, THUMB_H / orig_h)
        draw_w = orig_w * ratio
        draw_h = orig_h * ratio

        img = Image(buf, width=draw_w, height=draw_h)
        img.hAlign = 'CENTER'
        return img
    except Exception:
        return ''


def _build_table_for_selos(selos: list[Selo]) -> Table:
    """Constrói uma tabela de selos em falta compacta, sem cor de fundo."""
    col_widths = [
        THUMB_W + 2 * mm,  # Placeholder col
        58 * mm,           # Título
        12 * mm,           # Ano
        16 * mm,           # Valor
        16 * mm,           # Nº Catálogo
        CONTENT_W - (THUMB_W + 2 + 58 + 12 + 16 + 16) * mm,  # Mundifil
    ]

    header_row = [
        Paragraph('', STYLE_CELL_HEADER),
        Paragraph('Selo', STYLE_CELL_HEADER),
        Paragraph('Ano', STYLE_CELL_HEADER),
        Paragraph('Valor', STYLE_CELL_HEADER),
        Paragraph('Catálogo', STYLE_CELL_HEADER),
        Paragraph('Mundifil', STYLE_CELL_HEADER),
    ]
    data: list[list[Any]] = [header_row]

    for selo in selos:
        thumb = _make_thumb(_resolve_image_path(selo))
        valor = f'{selo.denominacao:g} {selo.moeda}'
        row = [
            thumb,
            Paragraph(selo.titulo, STYLE_CELL),
            Paragraph(str(selo.ano), STYLE_CELL),
            Paragraph(valor, STYLE_CELL),
            Paragraph(selo.numero_catalogo, STYLE_CELL),
            Paragraph(selo.numero_mundifil or '—', STYLE_CELL),
        ]
        data.append(row)

    table = Table(data, colWidths=col_widths, repeatRows=1)

    # Alturas: header fino, linhas de dados com altura fixa (placeholder)
    row_heights = [4.5 * mm] + [ROW_H] * len(selos)
    table._rowHeights = row_heights

    light_grey = colors.HexColor('#f5f5f5')
    border_color = colors.HexColor('#dddddd')
    header_bg = colors.HexColor('#e8e8e8')

    estilo = TableStyle([
        # Header
        ('BACKGROUND', (0, 0), (-1, 0), header_bg),
        ('FONTSIZE', (0, 0), (-1, 0), 6),
        # Body
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 0.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0.5),
        ('LEFTPADDING', (0, 0), (-1, -1), 1.5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 1.5),
        # Linhas alternadas (cinza muito claro)
        *[
            ('BACKGROUND', (0, i), (-1, i), light_grey)
            for i in range(2, len(data), 2)
        ],
        # Borda inferior do header
        ('LINEBELOW', (0, 0), (-1, 0), 0.5, border_color),
        # Bordas finas entre linhas
        ('LINEBELOW', (0, 1), (-1, -1), 0.25, colors.HexColor('#eeeeee')),
        # Borda do placeholder da imagem (coluna 0, linhas de dados)
        *[
            ('BOX', (0, i), (0, i), 0.25, border_color)
            for i in range(1, len(data))
        ],
    ])
    table.setStyle(estilo)
    return table


# ── Função principal ─────────────────────────────────────────────────────────


def gerar_pdf_faltas(utilizador: User, pais: Pais) -> bytes:
    """Gera um PDF com os selos em falta do utilizador para o país dado.

    Selos em falta = todos os selos do catálogo do país
                     menos os que o utilizador já possui na coleção.
    Ordenação: ano, série, denominação.
    """
    # IDs dos selos que o utilizador já tem
    ids_possuidos = set(
        utilizador.itens_colecao
        .filter(stamp__pais=pais)
        .values_list('stamp_id', flat=True)
    )

    selos_falta = (
        Selo.objects
        .filter(pais=pais)
        .exclude(pk__in=ids_possuidos)
        .select_related('serie')
        .order_by('ano', 'serie__nome', 'denominacao')
    )

    total_catalogo = Selo.objects.filter(pais=pais).count()
    total_falta = selos_falta.count()

    # Agrupar por série
    def serie_key(selo: Selo) -> str:
        return selo.serie.nome if selo.serie else 'Sem série'

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=MARGIN,
        title=f'Lista de Faltas – {pais.nome}',
        author='myStampsCollection',
    )

    story: list[Any] = []

    # Título
    story.append(Paragraph(f'Lista de Faltas – {pais.nome}', STYLE_TITLE))
    story.append(Paragraph(
        f'{total_falta} selos em falta de {total_catalogo} no catálogo '
        f'({total_catalogo - total_falta} na coleção)',
        STYLE_SUBTITLE,
    ))

    # Agrupar selos por série
    selos_list = list(selos_falta)
    if not selos_list:
        story.append(Paragraph(
            'Parabéns! Tens todos os selos deste país.',
            STYLE_CELL,
        ))
    else:
        for serie_nome, grupo in groupby(selos_list, key=serie_key):
            selos_grupo = list(grupo)
            ano_min = selos_grupo[0].ano
            ano_max = selos_grupo[-1].ano
            periodo = str(ano_min) if ano_min == ano_max else f'{ano_min}–{ano_max}'
            story.append(Paragraph(
                f'{serie_nome} ({periodo}) — {len(selos_grupo)} selo(s)',
                STYLE_SERIE,
            ))
            story.append(_build_table_for_selos(selos_grupo))
            story.append(Spacer(1, 2 * mm))

    # Rodapé com data
    from datetime import datetime
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(
        f'Gerado em {datetime.now():%Y-%m-%d %H:%M} · myStampsCollection',
        ParagraphStyle(
            'Rodape',
            parent=_BASE_STYLES['Normal'],
            fontSize=6,
            textColor=colors.HexColor('#999999'),
            alignment=1,
        ),
    ))

    doc.build(story)
    return buffer.getvalue()
