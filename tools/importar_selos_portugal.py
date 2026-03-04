"""Script para importar os selos portugueses do catálogo StampData.

Fonte: https://www.stampdata.com/ (emissor Portugal, ID=39)
Total de selos disponíveis: ~4911

Execução (dentro do container Docker):
    docker-compose exec web python tools/importar_selos_portugal.py

Ou localmente (com venv ativo):
    pip install requests beautifulsoup4 lxml
    python tools/importar_selos_portugal.py

O script guarda cache JSON em tools/cache_stampdata/ para poder
recomeçar se for interrompido.
"""

import json
import os
import re
import sys
import time
from decimal import Decimal, InvalidOperation
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

from catalog.models import Pais, Selo, Tema  # noqa: E402

# ─── Constantes ───────────────────────────────────────────────────────────────
BASE_URL = "https://www.stampdata.com"
ISSUER_ID = 39  # Portugal
PAGE_SIZE = 50
REQUEST_DELAY = 1.5  # segundos entre pedidos (respeito pelas regras do site)
CACHE_DIR = Path(__file__).parent / "cache_stampdata"
CACHE_LISTA = CACHE_DIR / "lista_ids_pt.json"
CACHE_DETALHES = CACHE_DIR / "detalhes_pt"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; MyStampsCollectionBot/1.0; "
        "academic research; contact: github.com/mbangas/myStampsCollection)"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# Mapas de moeda por contexto histórico (Portugal)
# Réis: até 1911 | Centavo/Escudo: 1911-2001 | Euro: 2002+
MOEDA_ESCUDO = "Esc"
MOEDA_REAL = "r"
MOEDA_EUR = "EUR"
MOEDA_CENTAVO = "ctvs"


# ─── Funções de utilidade ─────────────────────────────────────────────────────

def criar_diretorios_cache() -> None:
    """Cria as pastas de cache se não existirem."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DETALHES.mkdir(parents=True, exist_ok=True)


def fazer_pedido(url: str, tentativas: int = 3) -> Optional[BeautifulSoup]:
    """Faz um pedido HTTP com retry e devolve BeautifulSoup ou None."""
    for tentativa in range(tentativas):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            return BeautifulSoup(resp.text, "lxml")
        except requests.RequestException as exc:
            espera = REQUEST_DELAY * (tentativa + 1) * 2
            print(f"  ⚠ Erro ao aceder {url}: {exc}. Aguarda {espera}s...")
            time.sleep(espera)
    print(f"  ✗ Falhou após {tentativas} tentativas: {url}")
    return None


def parse_denominacao(denom_raw: str) -> tuple[Optional[Decimal], str]:
    """
    Converte a denominação em bruto (ex: '5r', '1.20€', '1E60', '$04')
    para (valor_decimal, moeda).

    Exemplos de denominações portuguesas:
    - Réis (pré-1911): '5r', '25r', '100r', '2½r'
    - Escudos (1912–2001): '5c', '$04', '1E20', '2E50', '100$00'
    - Euros (2002+): '0.30€', '1.20 €', '3.00'
    """
    if not denom_raw:
        return None, "?"

    d = denom_raw.strip()

    # Euro pós-2002 com símbolo '€'
    if "€" in d:
        num_str = d.replace("€", "").replace(",", ".").strip()
        try:
            return Decimal(num_str).quantize(Decimal("0.01")), MOEDA_EUR
        except InvalidOperation:
            return None, MOEDA_EUR

    # Réis: termina em 'r' ou 'rs'
    if re.match(r"^\d+[\u00bd½]?\s*r(?:s)?$", d, re.IGNORECASE):
        num_str = re.sub(r"[r\s]", "", d, flags=re.IGNORECASE)
        num_str = num_str.replace("½", ".5").replace("\u00bd", ".5")
        try:
            return Decimal(num_str).quantize(Decimal("0.01")), MOEDA_REAL
        except InvalidOperation:
            return None, MOEDA_REAL

    # Escudos: formato '1E20' ou '1$20' ou '100$00' ou 'n$nn'
    escudo_match = re.match(r"^(\d+)[\$E](\d{2})$", d, re.IGNORECASE)
    if escudo_match:
        escudos = int(escudo_match.group(1))
        centavos = int(escudo_match.group(2))
        valor = Decimal(escudos) + Decimal(centavos) / 100
        return valor.quantize(Decimal("0.01")), MOEDA_ESCUDO

    # Apenas centavos: '$04' ou '5c'
    centavo_match = re.match(r"^\$(\d+)$", d)
    if centavo_match:
        valor = Decimal(centavo_match.group(1)) / 100
        return valor.quantize(Decimal("0.01")), MOEDA_ESCUDO

    if re.match(r"^\d+c$", d, re.IGNORECASE):
        num_str = d[:-1]
        try:
            return Decimal(num_str).quantize(Decimal("0.01")), MOEDA_CENTAVO
        except InvalidOperation:
            return None, MOEDA_CENTAVO

    # Número simples (provavelmente euros modernos sem símbolo)
    plain_match = re.match(r"^(\d+(?:[.,]\d+)?)$", d)
    if plain_match:
        num_str = plain_match.group(1).replace(",", ".")
        try:
            return Decimal(num_str).quantize(Decimal("0.01")), MOEDA_EUR
        except InvalidOperation:
            return None, MOEDA_EUR

    # Fallback: tenta extrair número seguido de qualquer coisa
    generico = re.match(r"^([\d.,½\u00bd]+)\s*(.*)$", d)
    if generico:
        num_str = generico.group(1).replace(",", ".").replace("½", ".5")
        moeda = generico.group(2).strip() or "?"
        try:
            return Decimal(num_str).quantize(Decimal("0.01")), moeda
        except InvalidOperation:
            pass

    return None, d[:10]  # guardamos os 10 primeiros chars como moeda raw


def extrair_texto_celula(soup: BeautifulSoup, label: str) -> str:
    """Extrai o texto de uma célula de tabela dada a label na célula anterior."""
    for td in soup.select("td"):
        if td.get_text(strip=True) == label:
            next_td = td.find_next_sibling("td")
            if next_td:
                return next_td.get_text(strip=True)
    return ""


# ─── Fase 1: Obter todos os IDs da listagem ───────────────────────────────────

def obter_total_selos() -> int:
    """Obtém o número total de selos de Portugal no StampData."""
    url = f"{BASE_URL}/stamps.php?fissuer={ISSUER_ID}"
    soup = fazer_pedido(url)
    if not soup:
        return 0
    texto = soup.get_text()
    match = re.search(r"1 to \d+ of (\d+)", texto)
    if match:
        return int(match.group(1))
    return 0


def obter_ids_da_pagina(offset: int) -> list[int]:
    """Obtém os IDs dos selos de uma página da listagem via regex no HTML."""
    url = f"{BASE_URL}/stamps.php?fissuer={ISSUER_ID}&offset={offset}"
    for tentativa in range(3):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            # Links têm formato relativo: stamp.php?id=XXXXXX
            ids_raw = re.findall(r"stamp\.php\?id=(\d+)", resp.text)
            return list(dict.fromkeys(int(i) for i in ids_raw))
        except requests.RequestException as exc:
            espera = REQUEST_DELAY * (tentativa + 1) * 2
            print(f"  ⚠ Erro na página offset={offset}: {exc}. Aguarda {espera}s...")
            time.sleep(espera)
    return []


def obter_todos_os_ids() -> list[int]:
    """
    Obtém todos os IDs dos selos portugueses percorrendo a paginação.
    Guarda em cache para não repetir.
    """
    if CACHE_LISTA.exists():
        with open(CACHE_LISTA, encoding="utf-8") as f:
            ids = json.load(f)
        print(f"  ✓ {len(ids)} IDs carregados do cache.")
        return ids

    total = obter_total_selos()
    print(f"  → Total de selos em StampData (Portugal): {total}")
    if total == 0:
        print("  ✗ Não foi possível determinar o total.")
        return []

    todos_ids: list[int] = []
    paginas = (total + PAGE_SIZE - 1) // PAGE_SIZE

    for pagina in range(paginas):
        offset = pagina * PAGE_SIZE
        print(f"  → Página {pagina + 1}/{paginas} (offset={offset})...", end=" ")
        ids_pagina = obter_ids_da_pagina(offset)
        print(f"{len(ids_pagina)} IDs")
        todos_ids.extend(ids_pagina)
        time.sleep(REQUEST_DELAY)

    # Remove duplicados preservando ordem
    vistos: set[int] = set()
    ids_unicos = [i for i in todos_ids if not (i in vistos or vistos.add(i))]

    with open(CACHE_LISTA, "w", encoding="utf-8") as f:
        json.dump(ids_unicos, f)
    print(f"  ✓ {len(ids_unicos)} IDs únicos guardados em cache.")
    return ids_unicos


# ─── Fase 2: Scrape de cada página de detalhe ─────────────────────────────────

def caminho_cache_detalhe(stamp_id: int) -> Path:
    """Devolve o caminho do ficheiro de cache para um dado stamp_id."""
    return CACHE_DETALHES / f"{stamp_id}.json"


def scrape_detalhe_selo(stamp_id: int) -> Optional[dict]:
    """
    Faz scrape da página de detalhe de um selo e devolve um dicionário
    com os dados relevantes.
    """
    cache_path = caminho_cache_detalhe(stamp_id)
    if cache_path.exists():
        with open(cache_path, encoding="utf-8") as f:
            return json.load(f)

    url = f"{BASE_URL}/stamp.php?id={stamp_id}"
    soup = fazer_pedido(url)
    if not soup:
        return None

    dados: dict = {"id": stamp_id, "url": url}

    # ── Tabela de metadados ──────────────────────────────────────────────────
    dados["funcao"] = extrair_texto_celula(soup, "Function:")
    dados["data_iso"] = extrair_texto_celula(soup, "Date:")
    dados["issue"] = extrair_texto_celula(soup, "Issue:")
    dados["denominacao_raw"] = extrair_texto_celula(soup, "Denom:")
    dados["cor"] = extrair_texto_celula(soup, "Color:")
    dados["design_type"] = extrair_texto_celula(soup, "Design type:")
    dados["design"] = extrair_texto_celula(soup, "Design:")
    dados["watermark"] = extrair_texto_celula(soup, "Watermark:")
    dados["dentado_raw"] = extrair_texto_celula(soup, "Perf:")
    dados["tiragem_raw"] = extrair_texto_celula(soup, "Printing quantity:")

    # ── Números de catálogo (Scott, Yvert, etc.) ─────────────────────────────
    numeros_catalogo = []
    cat_section = soup.find(string=re.compile(r"Catalog numbers?:"))
    if cat_section:
        parent = cat_section.find_parent()
        if parent:
            links_cat = parent.find_next_sibling()
            if links_cat:
                for a in links_cat.find_all("a"):
                    numeros_catalogo.append(a.get_text(strip=True))

    # Alternativa: procura links de catálogo inline (href relativo sem slash)
    if not numeros_catalogo:
        for tag in soup.select('a[href*="catalog.php"]'):
            texto = tag.get_text(strip=True)
            if texto:
                numeros_catalogo.append(texto)

    dados["numeros_catalogo"] = numeros_catalogo

    # ── Extrair ano da data ──────────────────────────────────────────────────
    data_raw = dados.get("data_iso", "")
    ano_match = re.search(r"\b(\d{4})\b", data_raw)
    dados["ano"] = int(ano_match.group(1)) if ano_match else None

    # Guarda em cache
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)

    return dados


def scrape_todos_os_detalhes(ids: list[int]) -> list[dict]:
    """Faz scrape dos detalhes de todos os selos, com cache e progresso."""
    detalhes = []
    total = len(ids)
    em_cache = sum(1 for i in ids if caminho_cache_detalhe(i).exists())
    print(f"  → {em_cache}/{total} já em cache. A scrape os restantes...")

    for idx, stamp_id in enumerate(ids, 1):
        cache_path = caminho_cache_detalhe(stamp_id)

        if cache_path.exists():
            with open(cache_path, encoding="utf-8") as f:
                dado = json.load(f)
        else:
            if idx % 50 == 0 or idx == 1:
                print(f"  → Scraped {idx - 1}/{total}...")
            dado = scrape_detalhe_selo(stamp_id)
            time.sleep(REQUEST_DELAY)

        if dado:
            detalhes.append(dado)

    print(f"  ✓ {len(detalhes)} selos scraped no total.")
    return detalhes


# ─── Fase 3: Importar para Django ────────────────────────────────────────────

MAPEAMENTO_TEMAS = {
    "bird": "Fauna",
    "fish": "Fauna",
    "animal": "Fauna",
    "fauna": "Fauna",
    "mammal": "Fauna",
    "insect": "Fauna",
    "reptile": "Fauna",
    "flower": "Flora",
    "plant": "Flora",
    "flora": "Flora",
    "tree": "Flora",
    "sport": "Desporto",
    "athletics": "Desporto",
    "football": "Desporto",
    "painting": "Arte",
    "art": "Arte",
    "sculpture": "Arte",
    "architecture": "Arquitectura",
    "church": "Arquitectura",
    "castle": "Arquitectura",
    "monument": "Arquitectura",
    "bridge": "Arquitectura",
    "history": "História",
    "historical": "História",
    "person": "Personagens",
    "portrait": "Personagens",
    "king": "Personagens",
    "queen": "Personagens",
    "president": "Personagens",
    "ship": "Transportes",
    "airplane": "Transportes",
    "train": "Transportes",
    "car": "Transportes",
    "space": "Espaço",
    "satellite": "Espaço",
    "nature": "Natureza",
    "landscape": "Natureza",
    "map": "Natureza",
}


def obter_ou_criar_tema(nome: str) -> Optional[Tema]:
    """Obtém ou cria um Tema pelo nome."""
    if not nome:
        return None
    tema, _ = Tema.objects.get_or_create(nome=nome)
    return tema


def inferir_temas(dados: dict) -> list[Tema]:
    """Infere temas a partir dos campos de design e issue do selo."""
    texto = " ".join([
        dados.get("design", ""),
        dados.get("design_type", ""),
        dados.get("issue", ""),
    ]).lower()

    temas_encontrados = []
    nomes_ja_vistos: set[str] = set()

    for palavra, nome_tema in MAPEAMENTO_TEMAS.items():
        if palavra in texto and nome_tema not in nomes_ja_vistos:
            tema = obter_ou_criar_tema(nome_tema)
            if tema:
                temas_encontrados.append(tema)
                nomes_ja_vistos.add(nome_tema)

    return temas_encontrados


def build_numero_catalogo(dados: dict) -> str:
    """
    Constrói o número de catálogo a partir dos dados StampData.
    Prioridade: Scott number > outros catálogos > ID interno StampData.
    """
    numeros = dados.get("numeros_catalogo", [])
    # Procura número Scott (prefixo "Sc ")
    for n in numeros:
        if n.startswith("Sc "):
            return n
    # Qualquer outro número de catálogo
    if numeros:
        return numeros[0]
    # Fallback: ID interno StampData
    return f"SD-{dados['id']}"


def build_titulo(dados: dict) -> str:
    """Constrói o título do selo a partir dos campos disponíveis."""
    # Preferência: design > design_type > issue
    design = dados.get("design", "").strip()
    design_type = dados.get("design_type", "").strip()
    issue = dados.get("issue", "").strip()

    if design and design != design_type:
        return design[:200]
    if design_type:
        return design_type[:200]
    if issue:
        return issue[:200]
    return f"Selo Portugal ({dados.get('ano', '?')})"


def build_descricao_tematica(dados: dict) -> str:
    """Constrói a descrição temática do selo."""
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
    return " | ".join(partes) if partes else "Selo português."


def build_descricao_tecnica(dados: dict) -> str:
    """Constrói a descrição técnica a partir dos metadados StampData."""
    partes = []
    if dados.get("funcao"):
        funcoes_pt = {
            "postage": "Correio",
            "airmail": "Correio Aéreo",
            "official": "Serviço Oficial",
            "newspaper": "Jornais",
            "parcel post": "Encomendas",
            "express": "Expresso",
            "due": "Porteado",
        }
        nome_pt = funcoes_pt.get(dados["funcao"].lower(), dados["funcao"])
        partes.append(f"Função: {nome_pt}")
    if dados.get("cor"):
        partes.append(f"Cor: {dados['cor']}")
    if dados.get("watermark"):
        partes.append(f"Filigrana: {dados['watermark']}")
    if dados.get("dentado_raw"):
        partes.append(f"Dentado: {dados['dentado_raw']}")
    return " | ".join(partes) if partes else ""


def parse_tiragem(tiragem_raw: str) -> Optional[int]:
    """Converte a tiragem em número inteiro."""
    if not tiragem_raw:
        return None
    clean = re.sub(r"[^\d]", "", tiragem_raw)
    try:
        return int(clean) if clean else None
    except ValueError:
        return None


def importar_selos(detalhes: list[dict], portugal: Pais) -> tuple[int, int, int]:
    """
    Importa os selos para a base de dados Django.
    Devolve (criados, atualizados, ignorados).
    """
    criados = atualizados = ignorados = 0

    for idx, dados in enumerate(detalhes, 1):
        if idx % 100 == 0:
            print(f"  → Importados {idx}/{len(detalhes)}...")

        # Verificação mínima: precisa de ano
        ano = dados.get("ano")
        if not ano:
            ignorados += 1
            continue

        numero_catalogo = build_numero_catalogo(dados)
        titulo = build_titulo(dados)
        denom_valor, moeda = parse_denominacao(dados.get("denominacao_raw", ""))

        # Denominação nula é problemática; usa 0.00 como fallback
        if denom_valor is None:
            denom_valor = Decimal("0.00")

        descricao_tematica = build_descricao_tematica(dados)
        descricao_tecnica = build_descricao_tecnica(dados)
        dentado = dados.get("dentado_raw", "")[:50]
        tiragem = parse_tiragem(dados.get("tiragem_raw", ""))

        try:
            selo, criado = Selo.objects.update_or_create(
                pais=portugal,
                numero_catalogo=numero_catalogo,
                defaults={
                    "titulo": titulo,
                    "ano": ano,
                    "denominacao": denom_valor,
                    "moeda": moeda[:10],
                    "descricao_tematica": descricao_tematica,
                    "descricao_tecnica": descricao_tecnica,
                    "dentado": dentado,
                    "tiragem": tiragem,
                },
            )

            temas = inferir_temas(dados)
            if temas:
                selo.temas.set(temas)

            if criado:
                criados += 1
            else:
                atualizados += 1

        except Exception as exc:  # noqa: BLE001
            print(f"  ⚠ Erro ao importar stamp_id={dados['id']}: {exc}")
            ignorados += 1

    return criados, atualizados, ignorados


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    """Função principal que orquestra o processo de importação."""
    print("=" * 60)
    print("  Importação de Selos Portugueses – StampData.com")
    print("=" * 60)

    criar_diretorios_cache()

    # Garante que Portugal existe na BD
    portugal, criado_pais = Pais.objects.get_or_create(
        codigo_iso="PT",
        defaults={
            "nome": "Portugal",
            "descricao": (
                "Portugal, país da Península Ibérica, com tradição filatélica "
                "desde 1853, quando emitiu os seus primeiros selos com a imagem "
                "da rainha D. Maria II."
            ),
        },
    )
    if criado_pais:
        print(f"  ✓ País 'Portugal' criado na base de dados.")
    else:
        print(f"  ✓ País 'Portugal' já existe (ID={portugal.pk}).")

    # Garante que os temas base existem
    print("\n[1/3] A verificar temas base...")
    temas_base = [
        "Fauna", "Flora", "Desporto", "Arte", "Arquitectura",
        "História", "Personagens", "Transportes", "Espaço", "Natureza",
    ]
    for nome_tema in temas_base:
        Tema.objects.get_or_create(nome=nome_tema)
    print(f"  ✓ {len(temas_base)} temas garantidos.")

    # Fase 1: Obter lista de IDs
    print("\n[2/3] A obter lista de IDs dos selos (StampData)...")
    ids = obter_todos_os_ids()

    if not ids:
        print("  ✗ Sem IDs para processar. Verificar ligação à internet.")
        sys.exit(1)

    # Fase 2: Scrape dos detalhes
    print(f"\n[3/3] A fazer scrape de {len(ids)} selos...")
    print("      (usa cache em tools/cache_stampdata/ – pode ser retomado)")
    detalhes = scrape_todos_os_detalhes(ids)

    # Fase 3: Importar para Django
    print("\n[4/4] A importar para a base de dados Django...")
    criados, atualizados, ignorados = importar_selos(detalhes, portugal)

    print("\n" + "=" * 60)
    print("  CONCLUÍDO")
    print(f"  ✓ Selos criados:     {criados}")
    print(f"  ✓ Selos atualizados: {atualizados}")
    print(f"  ⚠ Selos ignorados:  {ignorados}")
    total_bd = Selo.objects.filter(pais=portugal).count()
    print(f"  → Total Portugal na BD: {total_bd}")
    print("=" * 60)


if __name__ == "__main__":
    main()
