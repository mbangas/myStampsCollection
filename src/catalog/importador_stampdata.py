"""Motor genérico de importação do StampData para qualquer país.

Utilizado pelo endpoint de importação via web (vista_iniciar_importacao_stampdata).
Corre numa thread em background e actualiza ImportacaoCatalogo com o progresso.
"""

import json
import logging
import re
import time
import traceback
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Callable, Optional

import requests
from bs4 import BeautifulSoup
from django.conf import settings
from django.core.files.base import ContentFile
from django.db import close_old_connections

from catalog.models import ImportacaoCatalogo, Pais, Selo, Serie, Tema

logger = logging.getLogger(__name__)

# ─── Constantes ────────────────────────────────────────────────────────────────

BASE_URL = "https://www.stampdata.com"
PAGE_SIZE = 50
REQUEST_DELAY = 1.5

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; MyStampsCollectionBot/1.0; "
        "academic research; contact: github.com/mbangas/myStampsCollection)"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

_EXCLUIR_SRC = ("flag", "logo", "icon", "button", "blank.gif", "spacer", "arrow", "nav")

MAPEAMENTO_TEMAS = {
    "bird": "Fauna", "fish": "Fauna", "animal": "Fauna", "fauna": "Fauna",
    "mammal": "Fauna", "insect": "Fauna", "reptile": "Fauna",
    "flower": "Flora", "plant": "Flora", "flora": "Flora", "tree": "Flora",
    "sport": "Desporto", "athletics": "Desporto", "football": "Desporto",
    "painting": "Arte", "art": "Arte", "sculpture": "Arte",
    "architecture": "Arquitectura", "church": "Arquitectura",
    "castle": "Arquitectura", "monument": "Arquitectura", "bridge": "Arquitectura",
    "history": "História", "historical": "História",
    "person": "Personagens", "portrait": "Personagens",
    "king": "Personagens", "queen": "Personagens", "president": "Personagens",
    "ship": "Transportes", "airplane": "Transportes",
    "train": "Transportes", "car": "Transportes",
    "space": "Espaço", "satellite": "Espaço",
    "nature": "Natureza", "landscape": "Natureza", "map": "Natureza",
}

TEMAS_BASE = [
    "Fauna", "Flora", "Desporto", "Arte", "Arquitectura",
    "História", "Personagens", "Transportes", "Espaço", "Natureza",
]

FUNCOES_PT = {
    "postage": "Correio", "airmail": "Correio Aéreo",
    "official": "Serviço Oficial", "newspaper": "Jornais",
    "parcel post": "Encomendas", "express": "Expresso", "due": "Porteado",
}


# ─── Utilidades HTTP ────────────────────────────────────────────────────────────

def _fazer_pedido(url: str, tentativas: int = 3) -> Optional[BeautifulSoup]:
    """Faz um pedido HTTP com retry e devolve BeautifulSoup ou None."""
    for tentativa in range(tentativas):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            return BeautifulSoup(resp.text, "lxml")
        except requests.RequestException as exc:
            espera = REQUEST_DELAY * (tentativa + 1) * 2
            logger.warning("Erro ao aceder %s (tentativa %d): %s", url, tentativa + 1, exc)
            time.sleep(espera)
    logger.error("Falhou após %d tentativas: %s", tentativas, url)
    return None


def _extrair_texto_celula(soup: BeautifulSoup, label: str) -> str:
    """Extrai o texto de uma célula de tabela dada a label na célula anterior."""
    for td in soup.select("td"):
        if td.get_text(strip=True) == label:
            next_td = td.find_next_sibling("td")
            if next_td:
                return next_td.get_text(strip=True)
    return ""


# ─── Cache ──────────────────────────────────────────────────────────────────────

def _cache_dir(issuer_id: int) -> Path:
    """Pasta de cache para um issuer_id específico."""
    base = Path(settings.BASE_DIR) / "tools" / "cache_stampdata"
    return base / f"detalhes_{issuer_id}"


def _cache_lista(issuer_id: int) -> Path:
    """Ficheiro de cache com a lista de IDs."""
    base = Path(settings.BASE_DIR) / "tools" / "cache_stampdata"
    return base / f"lista_ids_{issuer_id}.json"


def _garantir_dirs_cache(issuer_id: int) -> None:
    """Cria as pastas de cache se não existirem."""
    _cache_dir(issuer_id).mkdir(parents=True, exist_ok=True)


def _caminho_cache_detalhe(issuer_id: int, stamp_id: int) -> Path:
    return _cache_dir(issuer_id) / f"{stamp_id}.json"


# ─── Fase 1: Obter IDs ──────────────────────────────────────────────────────────

def _obter_total_selos(issuer_id: int) -> int:
    """Obtém o número total de selos de um emissor no StampData."""
    url = f"{BASE_URL}/stamps.php?fissuer={issuer_id}"
    soup = _fazer_pedido(url)
    if not soup:
        return 0
    texto = soup.get_text()
    match = re.search(r"1 to \d+ of (\d+)", texto)
    return int(match.group(1)) if match else 0


def _obter_ids_da_pagina(issuer_id: int, offset: int) -> list[int]:
    """Obtém IDs dos selos de uma página paginada."""
    url = f"{BASE_URL}/stamps.php?fissuer={issuer_id}&offset={offset}"
    for tentativa in range(3):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            ids_raw = re.findall(r"stamp\.php\?id=(\d+)", resp.text)
            return list(dict.fromkeys(int(i) for i in ids_raw))
        except requests.RequestException as exc:
            espera = REQUEST_DELAY * (tentativa + 1) * 2
            logger.warning("Erro na página offset=%d: %s", offset, exc)
            time.sleep(espera)
    return []


def _obter_todos_os_ids(
    issuer_id: int,
    prog: Callable[[str], None],
) -> list[int]:
    """Obtém todos os IDs dos selos de um emissor, com cache."""
    cache = _cache_lista(issuer_id)
    if cache.exists():
        with open(cache, encoding="utf-8") as f:
            ids = json.load(f)
        prog(f"Lista de IDs carregada do cache ({len(ids)} IDs).")
        return ids

    total = _obter_total_selos(issuer_id)
    prog(f"Total de selos em StampData (issuer {issuer_id}): {total}")
    if total == 0:
        return []

    todos_ids: list[int] = []
    paginas = (total + PAGE_SIZE - 1) // PAGE_SIZE

    for pagina in range(paginas):
        offset = pagina * PAGE_SIZE
        prog(f"A obter IDs – página {pagina + 1}/{paginas}…")
        ids_pagina = _obter_ids_da_pagina(issuer_id, offset)
        todos_ids.extend(ids_pagina)
        time.sleep(REQUEST_DELAY)

    vistos: set[int] = set()
    ids_unicos = [i for i in todos_ids if not (i in vistos or vistos.add(i))]

    with open(cache, "w", encoding="utf-8") as f:
        json.dump(ids_unicos, f)
    prog(f"{len(ids_unicos)} IDs únicos guardados em cache.")
    return ids_unicos


# ─── Fase 2: Scrape de detalhes ─────────────────────────────────────────────────

def _scrape_detalhe_selo(issuer_id: int, stamp_id: int) -> Optional[dict]:
    """Faz scrape da página de detalhe de um selo e devolve um dict (com cache)."""
    cache_path = _caminho_cache_detalhe(issuer_id, stamp_id)
    if cache_path.exists():
        with open(cache_path, encoding="utf-8") as f:
            return json.load(f)

    url = f"{BASE_URL}/stamp.php?id={stamp_id}"
    soup = _fazer_pedido(url)
    if not soup:
        return None

    dados: dict = {"id": stamp_id, "url": url}
    dados["funcao"] = _extrair_texto_celula(soup, "Function:")
    dados["data_iso"] = _extrair_texto_celula(soup, "Date:")
    dados["issue"] = _extrair_texto_celula(soup, "Issue:")
    dados["denominacao_raw"] = _extrair_texto_celula(soup, "Denom:")
    dados["cor"] = _extrair_texto_celula(soup, "Color:")
    dados["design_type"] = _extrair_texto_celula(soup, "Design type:")
    dados["design"] = _extrair_texto_celula(soup, "Design:")
    dados["watermark"] = _extrair_texto_celula(soup, "Watermark:")
    dados["dentado_raw"] = _extrair_texto_celula(soup, "Perf:")
    dados["tiragem_raw"] = _extrair_texto_celula(soup, "Printing quantity:")

    numeros_catalogo: list[str] = []
    cat_section = soup.find(string=re.compile(r"Catalog numbers?:"))
    if cat_section:
        parent = cat_section.find_parent()
        if parent:
            links_cat = parent.find_next_sibling()
            if links_cat:
                for a in links_cat.find_all("a"):
                    numeros_catalogo.append(a.get_text(strip=True))
    if not numeros_catalogo:
        for tag in soup.select('a[href*="catalog.php"]'):
            texto = tag.get_text(strip=True)
            if texto:
                numeros_catalogo.append(texto)
    dados["numeros_catalogo"] = numeros_catalogo

    data_raw = dados.get("data_iso", "")
    ano_match = re.search(r"\b(\d{4})\b", data_raw)
    dados["ano"] = int(ano_match.group(1)) if ano_match else None

    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)

    return dados


# ─── Fase 3: Transformação e importação ────────────────────────────────────────

def _parse_denominacao(denom_raw: str) -> tuple[Optional[Decimal], str]:
    """Converte denominação em (valor, moeda). Versão genérica."""
    if not denom_raw:
        return None, "?"
    d = denom_raw.strip()

    if "€" in d:
        num_str = d.replace("€", "").replace(",", ".").strip()
        try:
            return Decimal(num_str).quantize(Decimal("0.01")), "EUR"
        except InvalidOperation:
            return None, "EUR"

    if "$" in d and not d.startswith("$"):
        num_str = d.replace("$", "").replace(",", ".").strip()
        try:
            return Decimal(num_str).quantize(Decimal("0.01")), "USD"
        except InvalidOperation:
            return None, "USD"

    if "£" in d:
        num_str = d.replace("£", "").replace(",", ".").strip()
        try:
            return Decimal(num_str).quantize(Decimal("0.01")), "GBP"
        except InvalidOperation:
            return None, "GBP"

    plain_match = re.match(r"^(\d+(?:[.,]\d+)?)$", d)
    if plain_match:
        num_str = plain_match.group(1).replace(",", ".")
        try:
            return Decimal(num_str).quantize(Decimal("0.01")), "EUR"
        except InvalidOperation:
            return None, "EUR"

    generico = re.match(r"^([\d.,½\u00bd]+)\s*(.*)$", d)
    if generico:
        num_str = generico.group(1).replace(",", ".").replace("½", ".5").replace("\u00bd", ".5")
        moeda = generico.group(2).strip() or "?"
        try:
            return Decimal(num_str).quantize(Decimal("0.01")), moeda[:10]
        except InvalidOperation:
            pass

    return None, d[:10]


def _parse_data_emissao(data_raw: str) -> Optional[date]:
    """Converte data em bruto do StampData para date (M/D/YYYY, M/YYYY, YYYY)."""
    if not data_raw:
        return None
    d = data_raw.strip()
    try:
        partes = d.split("/")
        if len(partes) == 3:
            return date(int(partes[2]), int(partes[0]), int(partes[1]))
        if len(partes) == 2:
            return date(int(partes[1]), int(partes[0]), 1)
        if re.match(r"^\d{4}$", d):
            return date(int(d), 1, 1)
    except (ValueError, IndexError):
        pass
    return None


def _parse_tiragem(tiragem_raw: str) -> Optional[int]:
    """Converte tiragem em número inteiro."""
    if not tiragem_raw:
        return None
    clean = re.sub(r"[^\d]", "", tiragem_raw)
    try:
        return int(clean) if clean else None
    except ValueError:
        return None


def _build_numero_catalogo(dados: dict) -> str:
    numeros = dados.get("numeros_catalogo", [])
    for n in numeros:
        if n.startswith("Sc "):
            return n
    if numeros:
        return numeros[0]
    return f"SD-{dados['id']}"


def _build_titulo(dados: dict, nome_pais: str) -> str:
    design = dados.get("design", "").strip()
    design_type = dados.get("design_type", "").strip()
    issue = dados.get("issue", "").strip()
    if design and design != design_type:
        return design[:200]
    if design_type:
        return design_type[:200]
    if issue:
        return issue[:200]
    return f"Selo {nome_pais} ({dados.get('ano', '?')})"


def _build_descricao_tematica(dados: dict) -> str:
    partes = []
    issue = dados.get("issue", "").strip()
    design_type = dados.get("design_type", "").strip()
    design = dados.get("design", "").strip()
    if issue:
        partes.append(f"Série: {issue}")
    if design_type:
        partes.append(f"Tema: {design_type}")
    if design and design != design_type:
        partes.append(f"Motivo: {design}")
    return " | ".join(partes) if partes else "Selo."


def _build_descricao_tecnica(dados: dict) -> str:
    partes = []
    if dados.get("funcao"):
        nome_pt = FUNCOES_PT.get(dados["funcao"].lower(), dados["funcao"])
        partes.append(f"Função: {nome_pt}")
    if dados.get("cor"):
        partes.append(f"Cor: {dados['cor']}")
    if dados.get("watermark"):
        partes.append(f"Filigrana: {dados['watermark']}")
    if dados.get("dentado_raw"):
        partes.append(f"Dentado: {dados['dentado_raw']}")
    return " | ".join(partes) if partes else ""


def _obter_ou_criar_tema(nome: str) -> Optional[Tema]:
    if not nome:
        return None
    tema, _ = Tema.objects.get_or_create(nome=nome)
    return tema


def _inferir_temas(dados: dict) -> list[Tema]:
    texto = " ".join([
        dados.get("design", ""),
        dados.get("design_type", ""),
        dados.get("issue", ""),
    ]).lower()
    encontrados: list[Tema] = []
    nomes_vistos: set[str] = set()
    for palavra, nome_tema in MAPEAMENTO_TEMAS.items():
        if palavra in texto and nome_tema not in nomes_vistos:
            tema = _obter_ou_criar_tema(nome_tema)
            if tema:
                encontrados.append(tema)
                nomes_vistos.add(nome_tema)
    return encontrados


def _obter_ou_criar_serie(
    nome_issue: str,
    data_raw: str,
    pais: Pais,
    cache_series: dict,
) -> Optional[Serie]:
    if not nome_issue:
        return None
    nome_issue = nome_issue.strip()[:200]
    if nome_issue in cache_series:
        return cache_series[nome_issue]
    data_emissao = _parse_data_emissao(data_raw)
    serie, criada = Serie.objects.get_or_create(
        pais=pais,
        nome=nome_issue,
        defaults={"data_emissao": data_emissao},
    )
    if not criada and data_emissao and not serie.data_emissao:
        serie.data_emissao = data_emissao
        serie.save(update_fields=["data_emissao"])
    cache_series[nome_issue] = serie
    return serie


# ─── Fase 4: Descarregar imagens ────────────────────────────────────────────────

def _resolver_url(src: str, page_url: str) -> str:
    if src.startswith("http"):
        return src
    if src.startswith("/"):
        return f"{BASE_URL}{src}"
    base = page_url.rsplit("/", 1)[0]
    return f"{base}/{src}"


def _extrair_url_imagem(soup: BeautifulSoup, stamp_id: int, page_url: str) -> Optional[str]:
    imgs = soup.find_all("img")
    for img in imgs:
        src = img.get("src", "").strip()
        if not src or any(x in src.lower() for x in _EXCLUIR_SRC):
            continue
        if re.search(r"\.(jpg|jpeg|png)$", src, re.IGNORECASE) and str(stamp_id) in src:
            return _resolver_url(src, page_url)
    for img in imgs:
        src = img.get("src", "").strip()
        if not src or any(x in src.lower() for x in _EXCLUIR_SRC):
            continue
        if re.search(r"\.(jpg|jpeg|png)$", src, re.IGNORECASE):
            return _resolver_url(src, page_url)
    return None


def _obter_url_imagem_da_cache(issuer_id: int, stamp_id: int) -> tuple[Optional[str], bool]:
    """Devolve (url_imagem, fez_pedido_http)."""
    cache_path = _caminho_cache_detalhe(issuer_id, stamp_id)
    dados: dict = {}
    if cache_path.exists():
        with open(cache_path, encoding="utf-8") as f:
            dados = json.load(f)

    if "imagem_url_scraped" in dados:
        return dados.get("imagem_url"), False

    page_url = f"{BASE_URL}/stamp.php?id={stamp_id}"
    imagem_url: Optional[str] = None
    try:
        resp = requests.get(page_url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        imagem_url = _extrair_url_imagem(soup, stamp_id, page_url)
    except requests.RequestException as exc:
        logger.warning("Erro HTTP ao obter imagem stamp_id=%d: %s", stamp_id, exc)

    dados["imagem_url"] = imagem_url
    dados["imagem_url_scraped"] = True
    if cache_path.exists():
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)

    return imagem_url, True


def _descarregar_bytes(url: str) -> Optional[bytes]:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        if "image" not in resp.headers.get("content-type", ""):
            return None
        return resp.content
    except requests.RequestException as exc:
        logger.warning("Erro ao descarregar imagem %s: %s", url, exc)
        return None


def _obter_stamp_id_de_numero(numero_catalogo: str, issuer_id: int) -> Optional[int]:
    """Obtém o StampData ID a partir do numero_catalogo do selo (via cache)."""
    if numero_catalogo.startswith("SD-"):
        try:
            return int(numero_catalogo[3:])
        except ValueError:
            pass
    # Tenta construir índice a partir dos ficheiros de cache
    cache_dir = _cache_dir(issuer_id)
    if not cache_dir.exists():
        return None
    for f in cache_dir.glob("*.json"):
        try:
            with open(f, encoding="utf-8") as fh:
                data = json.load(fh)
            numeros = data.get("numeros_catalogo", [])
            chave = next((n for n in numeros if n.startswith("Sc ")), None)
            if chave is None:
                chave = numeros[0] if numeros else f"SD-{data.get('id', '')}"
            if chave == numero_catalogo:
                return data.get("id")
        except (json.JSONDecodeError, KeyError, StopIteration):
            continue
    return None


# ─── Função principal de importação ─────────────────────────────────────────────

def executar_importacao(importacao_id: int) -> None:
    """Função principal a ser executada numa thread em background.

    Actualiza o objecto ImportacaoCatalogo com o progresso em tempo real.
    Deve ser invocada como alvo de threading.Thread.
    """
    # Garante conexão DB limpa nesta thread
    close_old_connections()

    try:
        importacao = ImportacaoCatalogo.objects.select_related("pais").get(pk=importacao_id)
    except ImportacaoCatalogo.DoesNotExist:
        logger.error("ImportacaoCatalogo id=%d não encontrado.", importacao_id)
        return

    pais = importacao.pais
    issuer_id = importacao.issuer_id
    nome_pais = pais.nome

    def prog(mensagem: str, **campos) -> None:
        """Actualiza a fase e campos opcionais no registo de importação."""
        close_old_connections()
        importacao.fase_atual = mensagem[:300]
        for campo, valor in campos.items():
            setattr(importacao, campo, valor)
        fields = ["fase_atual"] + list(campos.keys())
        try:
            importacao.save(update_fields=fields)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Erro ao guardar progresso: %s", exc)

    try:
        # ── Garantir temas base ────────────────────────────────────────────────
        prog("A garantir temas base…")
        for nome_tema in TEMAS_BASE:
            Tema.objects.get_or_create(nome=nome_tema)

        # ── Fase 1: Obter IDs ──────────────────────────────────────────────────
        prog("A preparar cache…")
        _garantir_dirs_cache(issuer_id)

        prog("A obter lista de IDs do StampData…")
        ids = _obter_todos_os_ids(issuer_id, lambda m: prog(m))

        if not ids:
            importacao.marcar_erro(
                "Não foi possível obter IDs. Verifique o Issuer ID ou a ligação à internet."
            )
            return

        importacao.total_ids = len(ids)
        importacao.save(update_fields=["total_ids"])
        prog(f"{len(ids)} IDs encontrados. A fazer scrape dos detalhes…")

        # ── Fase 2: Scrape detalhes ────────────────────────────────────────────
        detalhes: list[dict] = []
        for idx, stamp_id in enumerate(ids, 1):
            dado = _scrape_detalhe_selo(issuer_id, stamp_id)
            if dado:
                detalhes.append(dado)
            # Throttle para não sobrecarregar StampData
            if not _caminho_cache_detalhe(issuer_id, stamp_id).exists():
                time.sleep(REQUEST_DELAY)

            if idx % 50 == 0 or idx == len(ids):
                prog(
                    f"Scrape: {idx}/{len(ids)} selos processados…",
                    ids_processados=idx,
                )

        prog(f"Scrape concluído. {len(detalhes)} selos obtidos. A importar para a BD…",
             ids_processados=len(ids))

        # ── Fase 3: Importar para BD ───────────────────────────────────────────
        close_old_connections()
        criados = atualizados = erros_bd = 0
        series_cache: dict = {}

        for idx, dados in enumerate(detalhes, 1):
            ano = dados.get("ano")
            if not ano:
                erros_bd += 1
                continue

            numero_catalogo = _build_numero_catalogo(dados)
            titulo = _build_titulo(dados, nome_pais)
            denom_valor, moeda = _parse_denominacao(dados.get("denominacao_raw", ""))
            if denom_valor is None:
                denom_valor = Decimal("0.00")

            serie = _obter_ou_criar_serie(
                dados.get("issue", ""),
                dados.get("data_iso", ""),
                pais,
                series_cache,
            )

            try:
                selo, criado = Selo.objects.update_or_create(
                    pais=pais,
                    numero_catalogo=numero_catalogo,
                    defaults={
                        "titulo": titulo,
                        "ano": ano,
                        "denominacao": denom_valor,
                        "moeda": moeda[:10],
                        "descricao_tematica": _build_descricao_tematica(dados),
                        "descricao_tecnica": _build_descricao_tecnica(dados),
                        "dentado": dados.get("dentado_raw", "")[:50],
                        "tiragem": _parse_tiragem(dados.get("tiragem_raw", "")),
                        "serie": serie,
                    },
                )
                temas = _inferir_temas(dados)
                if temas:
                    selo.temas.set(temas)
                if criado:
                    criados += 1
                else:
                    atualizados += 1
            except Exception as exc:  # noqa: BLE001
                logger.warning("Erro ao importar stamp_id=%s: %s", dados.get("id"), exc)
                erros_bd += 1

            if idx % 100 == 0 or idx == len(detalhes):
                prog(
                    f"Importação BD: {idx}/{len(detalhes)} – "
                    f"criados={criados}, atualizados={atualizados}…",
                    selos_criados=criados,
                    selos_atualizados=atualizados,
                    erros_importacao=erros_bd,
                )

        importacao.selos_criados = criados
        importacao.selos_atualizados = atualizados
        importacao.erros_importacao = erros_bd
        importacao.save(update_fields=["selos_criados", "selos_atualizados", "erros_importacao"])

        # ── Fase 4: Descarregar imagens ────────────────────────────────────────
        from django.db.models import Q
        selos_sem_imagem = list(
            Selo.objects.filter(pais=pais)
            .filter(Q(imagem="") | Q(imagem__isnull=True))
            .order_by("numero_catalogo")
        )
        total_sem_imagem = len(selos_sem_imagem)
        prog(
            f"Importação concluída. A descarregar imagens ({total_sem_imagem} selos sem imagem)…",
            imagens_total=total_sem_imagem,
        )

        imagens_ok = 0
        for idx, selo in enumerate(selos_sem_imagem, 1):
            stamp_id = _obter_stamp_id_de_numero(selo.numero_catalogo, issuer_id)
            if stamp_id is None:
                if idx % 100 == 0 or idx == total_sem_imagem:
                    prog(
                        f"Imagens: {idx}/{total_sem_imagem}…",
                        imagens_processadas=idx,
                    )
                continue

            imagem_url, fez_pedido = _obter_url_imagem_da_cache(issuer_id, stamp_id)
            if fez_pedido:
                time.sleep(1.0)

            if not imagem_url:
                if idx % 100 == 0 or idx == total_sem_imagem:
                    prog(f"Imagens: {idx}/{total_sem_imagem}…", imagens_processadas=idx)
                continue

            img_bytes = _descarregar_bytes(imagem_url)
            if img_bytes:
                ext = imagem_url.rsplit(".", 1)[-1].split("?")[0].lower()
                if ext not in ("jpg", "jpeg", "png"):
                    ext = "jpg"
                filename = f"{issuer_id}_{stamp_id}.{ext}"
                try:
                    close_old_connections()
                    selo.imagem.save(filename, ContentFile(img_bytes), save=True)
                    imagens_ok += 1
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Erro ao guardar imagem selo %s: %s", selo.numero_catalogo, exc)
            else:
                time.sleep(1.0)

            if idx % 50 == 0 or idx == total_sem_imagem:
                prog(
                    f"Imagens: {idx}/{total_sem_imagem} ({imagens_ok} descarregadas)…",
                    imagens_processadas=idx,
                )

        prog(
            f"Concluído! Selos criados: {criados}, atualizados: {atualizados}, "
            f"imagens: {imagens_ok}/{total_sem_imagem}.",
            imagens_processadas=total_sem_imagem,
        )
        importacao.marcar_concluido()

    except Exception as exc:  # noqa: BLE001
        erro_msg = f"{exc}\n{traceback.format_exc()}"
        logger.error("Erro fatal na importação id=%d: %s", importacao_id, erro_msg)
        try:
            close_old_connections()
            importacao.marcar_erro(str(exc)[:2000])
        except Exception:  # noqa: BLE001
            pass
    finally:
        close_old_connections()
