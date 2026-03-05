"""Script para descarregar imagens dos selos espanhóis a partir do StampData.

Pré-requisito: ter corrido importar_selos_espanha.py
  (popula tools/cache_stampdata/detalhes_es/ e importa os selos na BD)

Execução (dentro do container Docker):
    docker-compose exec web python tools/descarregar_imagens_es.py

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
CODIGO_PAIS = "ES"
IMG_PREFIX = "es"
REQUEST_DELAY = 1.0
CACHE_DIR = Path(__file__).parent / "cache_stampdata"
CACHE_DETALHES = CACHE_DIR / "detalhes_es"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; MyStampsCollectionBot/1.0; "
        "academic research; contact: github.com/mbangas/myStampsCollection)"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

_EXCLUIR_SRC = ("flag", "logo", "icon", "button", "blank.gif", "spacer", "arrow", "nav")

_INDICE_CATALOGO: dict[str, int] | None = None


# ─── Funções auxiliares ───────────────────────────────────────────────────────

def _resolver_url(src: str, page_url: str) -> str:
    """Converte URL relativo em absoluto."""
    if src.startswith("http"):
        return src
    if src.startswith("/"):
        return f"{BASE_URL}{src}"
    base = page_url.rsplit("/", 1)[0]
    return f"{base}/{src}"


def extrair_url_imagem_da_pagina(
    soup: BeautifulSoup, stamp_id: int, page_url: str
) -> Optional[str]:
    """Extrai o URL da imagem principal do selo da página de detalhe."""
    imgs = soup.find_all("img")

    for img in imgs:
        src = img.get("src", "").strip()
        if not src:
            continue
        if any(x in src.lower() for x in _EXCLUIR_SRC):
            continue
        if re.search(r"\.(jpg|jpeg|png)$", src, re.IGNORECASE) and str(stamp_id) in src:
            return _resolver_url(src, page_url)

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
        print("  → A construir índice de catálogo a partir do cache...", flush=True)
        _INDICE_CATALOGO = _construir_indice_catalogo()
        print(f"  ✓ Índice com {len(_INDICE_CATALOGO)} entradas.", flush=True)
    return _INDICE_CATALOGO.get(numero_catalogo)


def obter_url_imagem(stamp_id: int) -> tuple[Optional[str], bool]:
    """Obtém o URL da imagem, usando cache ou fazendo scrape. Devolve (url, fez_pedido_http)."""
    cache_path = CACHE_DETALHES / f"{stamp_id}.json"
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
        imagem_url = extrair_url_imagem_da_pagina(soup, stamp_id, page_url)
    except requests.RequestException as exc:
        print(f"  ⚠ Erro HTTP stamp_id={stamp_id}: {exc}", flush=True)

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
        print(f"  ⚠ Erro ao descarregar imagem {url}: {exc}", flush=True)
        return None


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    """Função principal."""
    print("=" * 60, flush=True)
    print("  Descarregar Imagens – Selos Espanhóis (StampData)", flush=True)
    print("=" * 60, flush=True)

    if not CACHE_DETALHES.exists():
        print("  ⚠ Cache não encontrado em tools/cache_stampdata/detalhes_es/", flush=True)
        print("    Corra primeiro: python tools/importar_selos_espanha.py", flush=True)
        sys.exit(1)

    try:
        espanha = Pais.objects.get(codigo_iso=CODIGO_PAIS)
    except Pais.DoesNotExist:
        print("  ✗ Espanha não existe na BD.", flush=True)
        print("    Corra primeiro: python tools/importar_selos_espanha.py", flush=True)
        sys.exit(1)

    from django.db.models import Q
    selos_sem_imagem = list(
        Selo.objects.filter(pais=espanha)
        .filter(Q(imagem="") | Q(imagem__isnull=True))
        .order_by("numero_catalogo")
    )
    total_sem_imagem = len(selos_sem_imagem)

    if total_sem_imagem == 0:
        total_bd = Selo.objects.filter(pais=espanha).count()
        print(f"  ✓ Todos os {total_bd} selos já têm imagem. Nada a fazer.", flush=True)
        return

    total_bd = Selo.objects.filter(pais=espanha).count()
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
        filename = f"{IMG_PREFIX}_{stamp_id}.{ext}"

        try:
            selo.imagem.save(filename, ContentFile(img_bytes), save=True)
            descarregados += 1
        except Exception as exc:  # noqa: BLE001
            print(f"  ⚠ Erro ao guardar imagem selo {selo.numero_catalogo}: {exc}", flush=True)
            erros += 1

    print("\n" + "=" * 60, flush=True)
    print("  CONCLUÍDO", flush=True)
    print(f"  ✓ Imagens descarregadas:       {descarregados}", flush=True)
    print(f"  ⚠ Sem ID StampData (CSV/outro): {sem_id}", flush=True)
    print(f"  ⚠ Sem URL de imagem:            {sem_url}", flush=True)
    print(f"  ✗ Erros de download:            {erros}", flush=True)
    total_com_imagem = Selo.objects.filter(pais=espanha).exclude(imagem="").count()
    print(f"  → Total com imagem na BD:       {total_com_imagem}/{total_bd}", flush=True)
    print("=" * 60, flush=True)


if __name__ == "__main__":
    main()
