"""Script para descarregar imagens dos selos portugueses a partir do StampData.

Pré-requisito: ter corrido importar_selos_portugal.py
  (popula tools/cache_stampdata/ e importa os selos na BD)

Execução (dentro do container Docker):
    docker-compose exec web python tools/descarregar_imagens_pt.py

O script:
  1. Lê os ficheiros de cache JSON em tools/cache_stampdata/detalhes_pt/
  2. Para cada selo sem imagem na BD, extrai o URL da imagem da página StampData
     (guarda o URL no cache JSON para não repetir pedidos HTTP)
  3. Descarrega a imagem e guarda em media/selos/
  4. Actualiza o campo Selo.imagem na base de dados

É idempotente: salta selos que já têm imagem e URLs já em cache.
"""

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Optional

import django
import requests
from bs4 import BeautifulSoup

# ─── Configuração Django ───────────────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "stamps_config.settings")
django.setup()

from django.core.files.base import ContentFile  # noqa: E402
from catalog.models import Pais, Selo  # noqa: E402

# ─── Constantes ───────────────────────────────────────────────────────────────
BASE_URL = "https://www.stampdata.com"
REQUEST_DELAY = 1.0  # segundos entre pedidos HTTP (respeito pelas regras do site)
CACHE_DIR = Path(__file__).parent / "cache_stampdata"
CACHE_DETALHES = CACHE_DIR / "detalhes_pt"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; MyStampsCollectionBot/1.0; "
        "academic research; contact: github.com/mbangas/myStampsCollection)"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# Palavras que indicam imagens de navegação/interface (não selos)
_EXCLUIR_SRC = ("flag", "logo", "icon", "button", "blank.gif", "spacer", "arrow", "nav")

# Índice global (numero_catalogo → stamp_id) construído uma única vez
_INDICE_CATALOGO: dict[str, int] | None = None


# ─── Funções auxiliares ───────────────────────────────────────────────────────

def _resolver_url(src: str, page_url: str) -> str:
    """Converte URL relativo em absoluto."""
    if src.startswith("http"):
        return src
    if src.startswith("/"):
        return f"{BASE_URL}{src}"
    # Relativo ao directório da página
    base = page_url.rsplit("/", 1)[0]
    return f"{base}/{src}"


def extrair_url_imagem_da_pagina(
    soup: BeautifulSoup, stamp_id: int, page_url: str
) -> Optional[str]:
    """Extrai o URL da imagem principal do selo da página de detalhe.

    Estratégia:
    1. Procura <img> cujo src contenha o stamp_id (muito provável ser a imagem certa).
    2. Se não encontrar, devolve o primeiro .jpg/.png que não seja navegação.
    """
    imgs = soup.find_all("img")

    # Passagem 1: imagem que inclui o ID no src
    for img in imgs:
        src = img.get("src", "").strip()
        if not src:
            continue
        if any(x in src.lower() for x in _EXCLUIR_SRC):
            continue
        if re.search(r"\.(jpg|jpeg|png)$", src, re.IGNORECASE) and str(stamp_id) in src:
            return _resolver_url(src, page_url)

    # Passagem 2: qualquer imagem jpg/png que não seja interface
    for img in imgs:
        src = img.get("src", "").strip()
        if not src:
            continue
        if any(x in src.lower() for x in _EXCLUIR_SRC):
            continue
        if re.search(r"\.(jpg|jpeg|png)$", src, re.IGNORECASE):
            return _resolver_url(src, page_url)

    return None


def _construir_indice_catalogo() -> dict[str, int]:
    """Mapeia numero_catalogo → stamp_id lendo todos os ficheiros de cache."""
    if not CACHE_DETALHES.exists():
        return {}
    indice: dict[str, int] = {}
    for f in CACHE_DETALHES.glob("*.json"):
        try:
            with open(f, encoding="utf-8") as fh:
                data = json.load(fh)
            stamp_id = data.get("id")
            if not stamp_id:
                continue
            numeros = data.get("numeros_catalogo", [])
            chave = None
            for n in numeros:
                if n.startswith("Sc "):
                    chave = n
                    break
            if chave is None:
                chave = numeros[0] if numeros else f"SD-{stamp_id}"
            indice[chave] = stamp_id
        except (json.JSONDecodeError, KeyError):
            continue
    return indice


def obter_stamp_id(numero_catalogo: str) -> Optional[int]:
    """Obtém o StampData ID a partir do numero_catalogo do selo."""
    global _INDICE_CATALOGO
    if numero_catalogo.startswith("SD-"):
        try:
            return int(numero_catalogo[3:])
        except ValueError:
            pass
    if _INDICE_CATALOGO is None:
        print("  → A construir índice de catálogo a partir do cache...")
        _INDICE_CATALOGO = _construir_indice_catalogo()
        print(f"  ✓ Índice com {len(_INDICE_CATALOGO)} entradas.")
    return _INDICE_CATALOGO.get(numero_catalogo)


def obter_url_imagem(stamp_id: int) -> tuple[Optional[str], bool]:
    """Obtém o URL da imagem, usando cache ou fazendo scrape.

    Devolve (url, fez_pedido_http).
    Guarda o resultado no cache JSON para evitar pedidos repetidos.
    """
    cache_path = CACHE_DETALHES / f"{stamp_id}.json"
    dados: dict = {}
    if cache_path.exists():
        with open(cache_path, encoding="utf-8") as f:
            dados = json.load(f)

    # Já foi feito o scrape do URL de imagem (pode ser None se não encontrou)
    if "imagem_url_scraped" in dados:
        return dados.get("imagem_url"), False

    # Precisa fazer pedido HTTP
    page_url = f"{BASE_URL}/stamp.php?id={stamp_id}"
    imagem_url: Optional[str] = None
    try:
        resp = requests.get(page_url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        imagem_url = extrair_url_imagem_da_pagina(soup, stamp_id, page_url)
    except requests.RequestException as exc:
        print(f"  ⚠ Erro HTTP stamp_id={stamp_id}: {exc}")

    # Actualiza o cache com o resultado (mesmo que None)
    dados["imagem_url"] = imagem_url
    dados["imagem_url_scraped"] = True
    if cache_path.exists():
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)

    return imagem_url, True


def descarregar_bytes(url: str) -> Optional[bytes]:
    """Descarrega o conteúdo binário de um URL de imagem."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        ct = resp.headers.get("content-type", "")
        if "image" not in ct:
            return None
        return resp.content
    except requests.RequestException as exc:
        print(f"  ⚠ Erro ao descarregar imagem {url}: {exc}")
        return None


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    """Função principal."""
    print("=" * 60)
    print("  Descarregar Imagens – Selos Portugueses (StampData)")
    print("=" * 60)

    if not CACHE_DETALHES.exists():
        print("  ⚠ Cache não encontrado em tools/cache_stampdata/detalhes_pt/")
        print("    Corra primeiro: python tools/importar_selos_portugal.py")
        sys.exit(1)

    try:
        portugal = Pais.objects.get(codigo_iso="PT")
    except Pais.DoesNotExist:
        print("  ✗ Portugal não existe na BD.")
        print("    Corra primeiro: python tools/importar_selos_portugal.py")
        sys.exit(1)

    from django.db.models import Q
    selos_sem_imagem = list(
        Selo.objects.filter(pais=portugal)
        .filter(Q(imagem="") | Q(imagem__isnull=True))
        .order_by("numero_catalogo")
    )
    total_sem_imagem = len(selos_sem_imagem)

    if total_sem_imagem == 0:
        total_bd = Selo.objects.filter(pais=portugal).count()
        print(f"  ✓ Todos os {total_bd} selos já têm imagem. Nada a fazer.")
        return

    total_bd = Selo.objects.filter(pais=portugal).count()
    print(f"  → {total_sem_imagem}/{total_bd} selos ainda sem imagem.", flush=True)

    descarregados = 0
    sem_id = 0
    sem_url = 0
    erros = 0

    for idx, selo in enumerate(selos_sem_imagem, 1):
        if idx % 100 == 0:
            print(f"  → Processados {idx}/{total_sem_imagem}...", flush=True)

        stamp_id = obter_stamp_id(selo.numero_catalogo)
        if stamp_id is None:
            sem_id += 1
            continue

        imagem_url, fez_pedido = obter_url_imagem(stamp_id)
        if fez_pedido:
            time.sleep(REQUEST_DELAY)

        if not imagem_url:
            sem_url += 1
            continue

        img_bytes = descarregar_bytes(imagem_url)
        if not img_bytes:
            erros += 1
            time.sleep(REQUEST_DELAY)
            continue

        ext = imagem_url.rsplit(".", 1)[-1].split("?")[0].lower()
        if ext not in ("jpg", "jpeg", "png"):
            ext = "jpg"
        filename = f"pt_{stamp_id}.{ext}"

        try:
            selo.imagem.save(filename, ContentFile(img_bytes), save=True)
            descarregados += 1
        except Exception as exc:  # noqa: BLE001
            print(f"  ⚠ Erro ao guardar imagem selo {selo.numero_catalogo}: {exc}")
            erros += 1

    print("\n" + "=" * 60)
    print("  CONCLUÍDO")
    print(f"  ✓ Imagens descarregadas:       {descarregados}")
    print(f"  ⚠ Sem ID StampData (CSV/outro): {sem_id}")
    print(f"  ⚠ Sem URL de imagem:            {sem_url}")
    print(f"  ✗ Erros de download:            {erros}")
    total_com_imagem = Selo.objects.filter(pais=portugal).exclude(imagem="").count()
    print(f"  → Total com imagem na BD:       {total_com_imagem}/{total_bd}")
    print("=" * 60)


if __name__ == "__main__":
    main()
