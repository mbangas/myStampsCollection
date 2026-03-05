"""Vista da landing page do myStampsCollection."""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import requests
from bs4 import BeautifulSoup
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from catalog.models import Pais, Selo, Serie
from collection.models import ItemColecao

logger = logging.getLogger(__name__)

# ─── Constantes ───────────────────────────────────────────────────────────────

LINKS_UTEIS = [
    {
        'titulo': 'CTT Filatelia',
        'url': 'https://www.cttfilatelia.pt/',
        'descricao': 'Loja oficial de filatelia dos CTT – Correios de Portugal.',
        'icone': 'bi-envelope-paper',
    },
    {
        'titulo': 'StampWorld',
        'url': 'https://www.stampworld.com/',
        'descricao': 'Catálogo mundial de selos online e comunidade de coleccionadores.',
        'icone': 'bi-globe2',
    },
    {
        'titulo': 'Selos de Portugal – Carlos Kullberg',
        'url': (
            'https://www.geralforum.com/board/threads/'
            'livros-electr%C3%B3nicos-gratuitos-de-filatelia-e-books-free-'
            'sec%C3%A7%C3%A3o-2-2.742617/'
        ),
        'descricao': 'E-books gratuitos de filatelia portuguesa por Carlos Kullberg.',
        'icone': 'bi-book',
    },
    {
        'titulo': 'Facebook – Filatelia Portugal',
        'url': 'https://www.facebook.com/groups/filateliaportuguesa/',
        'descricao': 'Grupo de filatelia portuguesa no Facebook.',
        'icone': 'bi-facebook',
    },
    {
        'titulo': 'Facebook – Stamp Collecting',
        'url': 'https://www.facebook.com/groups/stampcollecting/',
        'descricao': 'Comunidade internacional de coleccionadores de selos.',
        'icone': 'bi-facebook',
    },
    {
        'titulo': 'Colnect – Selos',
        'url': 'https://colnect.com/pt/stamps',
        'descricao': 'Catálogo e comunidade de troca de selos em várias línguas.',
        'icone': 'bi-collection',
    },
]

NEWS_TIMEOUT = 6  # segundos

NEWS_SOURCES: list[dict[str, str]] = [
    {
        'nome': 'Linn\'s Stamp News',
        'url': 'https://www.linns.com/news/',
        'selector': 'h3 a, h2 a, .article-title a',
        'base_url': 'https://www.linns.com',
    },
    {
        'nome': 'StampWorld News',
        'url': 'https://www.stampworld.com/news/',
        'selector': 'h2 a, h3 a, .news-title a, article a',
        'base_url': 'https://www.stampworld.com',
    },
]

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    ),
}


# ─── Funções auxiliares ───────────────────────────────────────────────────────

def _fetch_news_from_source(source: dict) -> list[dict[str, str]]:
    """Obtém notícias de uma fonte externa via web scraping."""
    noticias: list[dict[str, str]] = []
    try:
        resp = requests.get(
            source['url'],
            headers=HEADERS,
            timeout=NEWS_TIMEOUT,
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'lxml')
        links = soup.select(source['selector'])

        seen_titles: set[str] = set()
        for link in links[:8]:
            titulo = link.get_text(strip=True)
            if not titulo or len(titulo) < 10 or titulo in seen_titles:
                continue
            seen_titles.add(titulo)

            href = link.get('href', '')
            if href and not href.startswith('http'):
                href = source['base_url'].rstrip('/') + '/' + href.lstrip('/')

            noticias.append({
                'titulo': titulo[:120],
                'url': href,
                'fonte': source['nome'],
            })
            if len(noticias) >= 5:
                break
    except Exception:
        logger.warning('Falha ao obter notícias de %s', source['nome'], exc_info=True)

    return noticias


def _obter_noticias() -> list[dict[str, str]]:
    """Obtém notícias de filatelia de várias fontes, em paralelo."""
    todas: list[dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=len(NEWS_SOURCES)) as executor:
        futures = {
            executor.submit(_fetch_news_from_source, src): src
            for src in NEWS_SOURCES
        }
        for future in as_completed(futures, timeout=NEWS_TIMEOUT + 2):
            try:
                todas.extend(future.result())
            except Exception:
                pass

    return todas[:10]


# ─── Vista ────────────────────────────────────────────────────────────────────

@login_required
def landing_page(request: HttpRequest) -> HttpResponse:
    """Landing page com resumo do site, notícias e links úteis."""
    # Estatísticas globais do catálogo
    total_paises = Pais.objects.count()
    total_selos = Selo.objects.count()
    total_series = Serie.objects.count()

    # Países com selos (para os links diretos)
    paises_com_selos = (
        Pais.objects.annotate(num_selos=Count('selos'))
        .filter(num_selos__gt=0)
        .order_by('-num_selos')
    )

    # Estatísticas pessoais do utilizador
    itens_user = ItemColecao.objects.filter(utilizador=request.user)
    total_colecao = itens_user.count()
    total_repetidos = (
        itens_user.aggregate(rep=Sum('quantidade_repetidos'))['rep'] or 0
    )

    # Notícias (runtime) – pode falhar silenciosamente
    try:
        noticias = _obter_noticias()
    except Exception:
        noticias = []

    context: dict[str, Any] = {
        'total_paises': total_paises,
        'total_selos': total_selos,
        'total_series': total_series,
        'paises_com_selos': paises_com_selos,
        'total_colecao': total_colecao,
        'total_repetidos': total_repetidos,
        'noticias': noticias,
        'links_uteis': LINKS_UTEIS,
    }

    return render(request, 'home/landing.html', context)
