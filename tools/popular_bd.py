"""
Script utilitário para popular a base de dados com dados de exemplo.
Executar com: python tools/popular_bd.py
(certifica-te que o ambiente virtual está ativo e DJANGO_SETTINGS_MODULE definido)
"""

import os
import sys
import django

# Configura o Django
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'stamps_config.settings')
django.setup()

from catalog.models import Pais, Selo, Tema  # noqa: E402


def criar_temas() -> list:
    """Cria temas de exemplo."""
    nomes_temas = [
        'Fauna', 'Flora', 'Desporto', 'Arte', 'Arquitectura',
        'História', 'Personagens', 'Transportes', 'Espaço', 'Natureza',
    ]
    temas = []
    for nome in nomes_temas:
        tema, _ = Tema.objects.get_or_create(nome=nome)
        temas.append(tema)
        print(f'  ✓ Tema: {nome}')
    return temas


def criar_paises() -> list:
    """Cria países de exemplo."""
    dados_paises = [
        ('Portugal', 'PT', 'País na Península Ibérica, com rica tradição filatélica.'),
        ('Brasil', 'BR', 'O maior país da América do Sul.'),
        ('Reino Unido', 'GB', 'Emitiu o primeiro selo do mundo — o Penny Black (1840).'),
        ('França', 'FR', 'Uma das maiores coleções filatélicas do mundo.'),
        ('Alemanha', 'DE', 'Selos com grande variedade temática.'),
        ('Estados Unidos', 'US', 'Um dos maiores emissores de selos mundiais.'),
        ('Japão', 'JP', 'Selos de alta qualidade artística.'),
        ('China', 'CN', 'Emissões de grande tiragem e diversidade.'),
        ('Austrália', 'AU', 'Fauna e flora únicas nos selos.'),
        ('Moçambique', 'MZ', 'Rica tradição de selos com fauna africana.'),
    ]
    paises = []
    for nome, codigo, desc in dados_paises:
        pais, _ = Pais.objects.get_or_create(
            codigo_iso=codigo,
            defaults={'nome': nome, 'descricao': desc}
        )
        paises.append(pais)
        print(f'  ✓ País: {nome}')
    return paises


def criar_selos_exemplo(paises: list, temas: list) -> None:
    """Cria alguns selos de exemplo."""
    portugal = next(p for p in paises if p.codigo_iso == 'PT')
    brasil = next(p for p in paises if p.codigo_iso == 'BR')
    fauna = next(t for t in temas if t.nome == 'Fauna')
    arte = next(t for t in temas if t.nome == 'Arte')
    historia = next(t for t in temas if t.nome == 'História')

    selos_dados = [
        {
            'pais': portugal,
            'numero_catalogo': 'PT-2024-001',
            'titulo': 'Lobo Ibérico',
            'ano': 2024,
            'denominacao': 1.00,
            'moeda': 'EUR',
            'descricao_tematica': 'O lobo ibérico (Canis lupus signatus), símbolo da natureza selvagem portuguesa.',
            'descricao_tecnica': 'Offset a 6 cores. Formato 30×40mm. Dentado 13½×13.',
            'dentado': '13½×13',
            'tiragem': 500000,
            'temas': [fauna],
        },
        {
            'pais': portugal,
            'numero_catalogo': 'PT-2023-015',
            'titulo': 'Azulejos Portugueses',
            'ano': 2023,
            'denominacao': 0.90,
            'moeda': 'EUR',
            'descricao_tematica': 'Padrões tradicionais dos azulejos portugueses do século XVIII.',
            'descricao_tecnica': 'Calcografia + offset. Formato 30×40mm.',
            'dentado': '14',
            'tiragem': 750000,
            'temas': [arte],
        },
        {
            'pais': brasil,
            'numero_catalogo': 'BR-2024-010',
            'titulo': 'Arara Azul',
            'ano': 2024,
            'denominacao': 3.50,
            'moeda': 'BRL',
            'descricao_tematica': 'A arara-azul-grande (Anodorhynchus hyacinthinus), espécie ameaçada do Pantanal.',
            'descricao_tecnica': 'Litografia a 5 cores. Formato 36×48mm. Dentado 12.',
            'dentado': '12',
            'tiragem': 1000000,
            'temas': [fauna],
        },
        {
            'pais': brasil,
            'numero_catalogo': 'BR-2023-008',
            'titulo': '200 Anos de Independência',
            'ano': 2022,
            'denominacao': 5.00,
            'moeda': 'BRL',
            'descricao_tematica': 'Commemoração dos 200 anos da Independência do Brasil (1822-2022).',
            'descricao_tecnica': 'Calcografia. Formato 40×50mm.',
            'dentado': '11½',
            'tiragem': 800000,
            'temas': [historia],
        },
    ]

    for dados in selos_dados:
        temas_selo = dados.pop('temas')
        selo, criado = Selo.objects.get_or_create(
            pais=dados['pais'],
            numero_catalogo=dados['numero_catalogo'],
            defaults=dados,
        )
        if criado:
            selo.temas.set(temas_selo)
            print(f'  ✓ Selo criado: {selo}')
        else:
            print(f'  – Selo já existe: {selo}')


if __name__ == '__main__':
    print('\n=== A popular base de dados com dados de exemplo ===\n')
    print('Temas:')
    temas = criar_temas()
    print('\nPaíses:')
    paises = criar_paises()
    print('\nSelos:')
    criar_selos_exemplo(paises, temas)
    print('\n✅ Concluído!\n')
