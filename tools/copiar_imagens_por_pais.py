"""Script para descarregar imagens dos selos e organizá-las por país.

Lê os ficheiros de cache JSON em tools/cache_stampdata/detalhes_pt/ e detalhes_es/,
extrai os URLs das imagens e descarrega-as para images/stamps/<ISO>/.

Execução:
    python tools/copiar_imagens_por_pais.py

É idempotente: salta imagens que já existam no destino.
"""

import json
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse

import requests

# ─── Constantes ───────────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT_DIR / "tools" / "cache_stampdata"
DEST_DIR = ROOT_DIR / "images" / "stamps"

# Mapeamento: pasta de cache → código ISO do país
PAISES = {
    "detalhes_pt": "PT",
    "detalhes_es": "ES",
}

MAX_WORKERS = 10
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; MyStampsCollectionBot/1.0; "
        "academic research; contact: github.com/mbangas/myStampsCollection)"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def _extensao_do_url(url: str) -> str:
    """Extrai a extensão do ficheiro a partir do URL."""
    caminho = urlparse(url).path
    _, ext = os.path.splitext(caminho)
    if ext.lower() in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
        return ext.lower()
    return ".jpg"


def descarregar_imagem(url: str, destino: Path, session: requests.Session) -> bool:
    """Descarrega uma imagem de um URL e guarda no destino."""
    try:
        resp = session.get(url, timeout=30)
        resp.raise_for_status()
        ct = resp.headers.get("content-type", "")
        if "image" not in ct:
            return False
        with open(destino, "wb") as f:
            f.write(resp.content)
        return True
    except requests.RequestException:
        return False


def _preparar_tarefas(pasta_cache: str, codigo_iso: str) -> list[tuple[str, Path]]:
    """Lê o cache e devolve lista de (url, destino) a descarregar."""
    cache_path = CACHE_DIR / pasta_cache
    dest_path = DEST_DIR / codigo_iso

    if not cache_path.exists():
        print(f"  ⚠ Cache não encontrado: {cache_path}")
        return []

    dest_path.mkdir(parents=True, exist_ok=True)
    tarefas: list[tuple[str, Path]] = []
    sem_url = 0
    ja_existentes = 0

    for ficheiro in sorted(cache_path.glob("*.json")):
        try:
            with open(ficheiro, encoding="utf-8") as fh:
                dados = json.load(fh)
        except (json.JSONDecodeError, OSError):
            continue

        stamp_id = dados.get("id", ficheiro.stem)
        url = dados.get("imagem_url") or dados.get("img_url", "")

        if not url:
            sem_url += 1
            continue

        ext = _extensao_do_url(url)
        destino = dest_path / f"{stamp_id}{ext}"

        if destino.exists():
            ja_existentes += 1
            continue

        tarefas.append((url, destino))

    total_cache = len(list(cache_path.glob("*.json")))
    print(f"  {codigo_iso}: {total_cache} fichas, {ja_existentes} já existem, "
          f"{sem_url} sem URL, {len(tarefas)} a descarregar")
    return tarefas


def processar_pais(pasta_cache: str, codigo_iso: str) -> None:
    """Processa todos os ficheiros de cache de um país com downloads paralelos."""
    print(f"\n{'=' * 60}")
    print(f"  País: {codigo_iso}")
    print(f"{'=' * 60}")

    tarefas = _preparar_tarefas(pasta_cache, codigo_iso)
    if not tarefas:
        print(f"  Nada a descarregar para {codigo_iso}.")
        return

    descarregados = 0
    erros = 0
    lock = threading.Lock()
    session = requests.Session()
    session.headers.update(HEADERS)

    def _download(url: str, destino: Path) -> bool:
        return descarregar_imagem(url, destino, session)

    total = len(tarefas)
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(_download, url, dest): (url, dest)
            for url, dest in tarefas
        }
        for i, future in enumerate(as_completed(futures), 1):
            ok = future.result()
            with lock:
                if ok:
                    descarregados += 1
                else:
                    erros += 1
                if i % 200 == 0:
                    print(
                        f"  → {i}/{total} "
                        f"(✓ {descarregados}, ✗ {erros})",
                        flush=True,
                    )

    print(f"\n  Resumo {codigo_iso}:")
    print(f"    ✓ Descarregados: {descarregados}")
    print(f"    ✗ Erros:        {erros}")
    print(f"    Total a fazer:  {total}")


def main() -> None:
    """Função principal."""
    print("=" * 60)
    print("  Descarregar Imagens de Selos por País")
    print(f"  Destino: {DEST_DIR}")
    print("=" * 60)

    DEST_DIR.mkdir(parents=True, exist_ok=True)

    for pasta_cache, codigo_iso in PAISES.items():
        processar_pais(pasta_cache, codigo_iso)

    print("\n✓ Concluído.")


if __name__ == "__main__":
    main()
