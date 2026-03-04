"""
Comando de gestão para importar países e selos a partir da pasta docs/.

Uso:
    python manage.py importar_catalogo
    python manage.py importar_catalogo --pais Espanha
    python manage.py importar_catalogo --apenas-paises
    python manage.py importar_catalogo --forcar
"""

import csv
import json
import os
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from catalog.models import Pais, Selo, Tema


DOCS_DIR = Path(settings.BASE_DIR) / 'docs'
FICHEIRO_PAIS = 'pais.json'
FICHEIRO_SELOS = 'selos.csv'

# Extensões ignoradas na listagem de documentos de referência
EXTENSOES_DADOS = {'.json', '.csv'}


class Command(BaseCommand):
    """Importa países e selos a partir da estrutura de pastas em docs/."""

    help = 'Importa países e selos a partir da pasta docs/'

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            '--pais',
            type=str,
            metavar='NOME',
            help='Importa apenas o país com este nome (igual ao nome da pasta).',
        )
        parser.add_argument(
            '--apenas-paises',
            action='store_true',
            help='Cria/atualiza países mas não importa selos.',
        )
        parser.add_argument(
            '--forcar',
            action='store_true',
            help='Força a atualização de selos já existentes.',
        )

    def handle(self, *args, **options) -> None:
        """Ponto de entrada do comando."""
        if not DOCS_DIR.exists():
            raise CommandError(f'A pasta docs/ não existe em: {DOCS_DIR}')

        filtro_pais = options.get('pais')
        apenas_paises = options['apenas_paises']
        forcar = options['forcar']

        pastas = self._listar_pastas_paises(filtro_pais)

        if not pastas:
            self.stdout.write(self.style.WARNING('Nenhuma pasta de país encontrada em docs/.'))
            return

        total_paises = 0
        total_selos = 0
        total_erros = 0

        for pasta in pastas:
            try:
                with transaction.atomic():
                    pais = self._importar_pais(pasta)
                    total_paises += 1

                    if not apenas_paises:
                        selos, erros = self._importar_selos(pasta, pais, forcar)
                        total_selos += selos
                        total_erros += erros
            except Exception as exc:
                self.stderr.write(
                    self.style.ERROR(f'  Erro a processar "{pasta.name}": {exc}')
                )
                total_erros += 1

        self._mostrar_resumo(total_paises, total_selos, total_erros, apenas_paises)

    # ─── Métodos auxiliares ────────────────────────────────────────────────────

    def _listar_pastas_paises(self, filtro: str | None) -> list[Path]:
        """Devolve a lista de subdiretorias de docs/ a processar."""
        pastas = sorted(
            p for p in DOCS_DIR.iterdir()
            if p.is_dir() and not p.name.startswith('.')
        )
        if filtro:
            pastas = [p for p in pastas if p.name == filtro]
            if not pastas:
                raise CommandError(
                    f'Pasta "{filtro}" não encontrada dentro de docs/. '
                    f'Pastas disponíveis: {[p.name for p in sorted(DOCS_DIR.iterdir()) if p.is_dir()]}'
                )
        return pastas

    def _importar_pais(self, pasta: Path) -> Pais:
        """Cria ou atualiza o país a partir da pasta e do pais.json opcional."""
        nome_pais = pasta.name
        ficheiro_json = pasta / FICHEIRO_PAIS

        defaults: dict = {}
        if ficheiro_json.exists():
            with ficheiro_json.open(encoding='utf-8') as f:
                dados = json.load(f)
            codigo_iso = dados.get('codigo_iso', '').strip().upper()
            if not codigo_iso:
                raise CommandError(
                    f'  {pasta.name}/pais.json não tem "codigo_iso" definido.'
                )
            defaults['nome'] = nome_pais
            defaults['descricao'] = dados.get('descricao', '')

            pais, criado = Pais.objects.update_or_create(
                codigo_iso=codigo_iso,
                defaults=defaults,
            )
        else:
            # Sem pais.json: cria com o nome da pasta; código ISO fica vazio se já não existir
            pais, criado = Pais.objects.get_or_create(
                nome=nome_pais,
                defaults={'codigo_iso': nome_pais[:3].upper()},
            )

        estado = self.style.SUCCESS('criado') if criado else self.style.WARNING('atualizado')
        self._listar_documentos_referencia(pasta)
        self.stdout.write(f'\n🌍 País: {pais.nome} ({pais.codigo_iso}) — {estado}')
        return pais

    def _listar_documentos_referencia(self, pasta: Path) -> None:
        """Lista os ficheiros de referência (PDFs, imagens, etc.) na pasta."""
        docs = [
            f.name for f in pasta.iterdir()
            if f.is_file() and f.suffix.lower() not in EXTENSOES_DADOS
        ]
        if docs:
            self.stdout.write(f'   📄 Documentos de referência: {", ".join(docs)}')

    def _importar_selos(self, pasta: Path, pais: Pais, forcar: bool) -> tuple[int, int]:
        """Importa selos do selos.csv dentro da pasta. Devolve (importados, erros)."""
        ficheiro_csv = pasta / FICHEIRO_SELOS

        if not ficheiro_csv.exists():
            self.stdout.write(f'   ℹ️  Sem {FICHEIRO_SELOS}, a saltar importação de selos.')
            return 0, 0

        importados = 0
        erros = 0

        with ficheiro_csv.open(encoding='utf-8', newline='') as f:
            leitor = csv.DictReader(f)
            self._validar_cabecalhos(leitor.fieldnames or [], ficheiro_csv)

            for numero_linha, linha in enumerate(leitor, start=2):
                try:
                    self._processar_linha_selo(linha, pais, forcar, numero_linha)
                    importados += 1
                except Exception as exc:
                    self.stderr.write(
                        self.style.ERROR(f'   ✗ Linha {numero_linha}: {exc}')
                    )
                    erros += 1

        self.stdout.write(
            f'   📮 Selos: {self.style.SUCCESS(str(importados))} importados'
            + (f', {self.style.ERROR(str(erros))} erros' if erros else '')
        )
        return importados, erros

    def _validar_cabecalhos(self, cabecalhos: list[str], ficheiro: Path) -> None:
        """Verifica que as colunas obrigatórias existem no CSV."""
        obrigatorias = {'numero_catalogo', 'titulo', 'ano', 'denominacao', 'moeda', 'descricao_tematica'}
        em_falta = obrigatorias - set(cabecalhos)
        if em_falta:
            raise CommandError(
                f'Colunas em falta em {ficheiro.name}: {", ".join(sorted(em_falta))}'
            )

    def _processar_linha_selo(
        self, linha: dict, pais: Pais, forcar: bool, numero_linha: int
    ) -> None:
        """Cria ou atualiza um selo a partir de uma linha do CSV."""
        numero_catalogo = linha['numero_catalogo'].strip()
        if not numero_catalogo:
            raise ValueError('numero_catalogo está vazio.')

        titulo = linha['titulo'].strip()
        ano_str = linha['ano'].strip()
        denominacao_str = linha['denominacao'].strip()
        moeda = linha['moeda'].strip()
        descricao_tematica = linha['descricao_tematica'].strip()

        if not all([titulo, ano_str, denominacao_str, moeda, descricao_tematica]):
            raise ValueError('Um ou mais campos obrigatórios estão vazios.')

        try:
            ano = int(ano_str)
        except ValueError:
            raise ValueError(f'Ano inválido: "{ano_str}"')

        try:
            denominacao = float(denominacao_str.replace(',', '.'))
        except ValueError:
            raise ValueError(f'Denominação inválida: "{denominacao_str}"')

        tiragem_str = linha.get('tiragem', '').strip()
        tiragem = None
        if tiragem_str:
            try:
                tiragem = int(tiragem_str)
            except ValueError:
                raise ValueError(f'Tiragem inválida: "{tiragem_str}"')

        defaults = {
            'titulo': titulo,
            'ano': ano,
            'denominacao': denominacao,
            'moeda': moeda,
            'descricao_tematica': descricao_tematica,
            'descricao_tecnica': linha.get('descricao_tecnica', '').strip(),
            'dentado': linha.get('dentado', '').strip(),
            'tiragem': tiragem,
        }

        if forcar:
            selo, criado = Selo.objects.update_or_create(
                pais=pais,
                numero_catalogo=numero_catalogo,
                defaults=defaults,
            )
        else:
            selo, criado = Selo.objects.get_or_create(
                pais=pais,
                numero_catalogo=numero_catalogo,
                defaults=defaults,
            )

        # Associar temas
        temas_str = linha.get('temas', '').strip()
        if temas_str and (criado or forcar):
            nomes_temas = [t.strip() for t in temas_str.split(';') if t.strip()]
            temas_objs = []
            for nome_tema in nomes_temas:
                tema, _ = Tema.objects.get_or_create(nome=nome_tema)
                temas_objs.append(tema)
            selo.temas.set(temas_objs)

    def _mostrar_resumo(
        self, paises: int, selos: int, erros: int, apenas_paises: bool
    ) -> None:
        """Mostra o resumo final da importação."""
        self.stdout.write('\n' + '─' * 50)
        self.stdout.write(self.style.SUCCESS('✅ Importação concluída'))
        self.stdout.write(f'   Países processados : {paises}')
        if not apenas_paises:
            self.stdout.write(f'   Selos importados   : {selos}')
        if erros:
            self.stdout.write(self.style.ERROR(f'   Erros              : {erros}'))
        self.stdout.write('─' * 50)
