"""
Comando de gestão para carregar o catálogo a partir das fixtures incluídas na imagem.

Garante que, em qualquer infraestrutura, os dados e as fotos estão disponíveis
imediatamente após o arranque do contentor, sem necessidade de re-importação.

Uso:
    python manage.py carregar_catalogo
    python manage.py carregar_catalogo --forcar   # recarrega mesmo que BD não esteja vazia
    python manage.py carregar_catalogo --sem-media # carrega só a BD, sem extrair imagens
"""

import tarfile
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand

from catalog.models import Selo

FIXTURES_DIR = Path(settings.BASE_DIR) / "fixtures"
FIXTURE_CATALOG = FIXTURES_DIR / "catalog.json"
FIXTURE_MEDIA = FIXTURES_DIR / "media_stamps.tar.gz"
MEDIA_SELOS_DIR = Path(settings.MEDIA_ROOT) / "selos"


class Command(BaseCommand):
    """Carrega o catálogo (BD + imagens) a partir das fixtures incluídas na imagem Docker."""

    help = (
        "Carrega o catálogo de selos a partir das fixtures incluídas na imagem. "
        "Salta automaticamente se a BD já tiver dados e o volume de media já tiver imagens."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--forcar",
            action="store_true",
            help="Força o recarregamento mesmo que a BD já tenha dados.",
        )
        parser.add_argument(
            "--sem-media",
            action="store_true",
            help="Carrega apenas a BD; não extrai o arquivo de imagens.",
        )

    def handle(self, *args, **options) -> None:
        """Ponto de entrada do comando."""
        forcar = options["forcar"]
        sem_media = options["sem_media"]

        self._carregar_bd(forcar)

        if not sem_media:
            self._extrair_media(forcar)

        self.stdout.write(self.style.SUCCESS("✅ Catálogo pronto."))

    # ── Base de dados ──────────────────────────────────────────────────────────

    def _carregar_bd(self, forcar: bool) -> None:
        """Carrega as fixtures na BD se esta estiver vazia (ou se --forcar)."""
        if not FIXTURE_CATALOG.exists():
            self.stdout.write(
                self.style.WARNING(
                    f"⚠  Fixture não encontrada: {FIXTURE_CATALOG}. "
                    "Cria-a com: python manage.py dumpdata catalog --indent 2 > fixtures/catalog.json"
                )
            )
            return

        bd_populada = Selo.objects.exists()

        if bd_populada and not forcar:
            count = Selo.objects.count()
            self.stdout.write(f"  ✓ BD já tem {count} selos — a saltar fixture.")
            return

        if bd_populada and forcar:
            self.stdout.write("  ⚠  --forcar activo: a recarregar a BD (loaddata substitui registos existentes).")

        self.stdout.write(f"  → A carregar fixtures de {FIXTURE_CATALOG}…")
        call_command("loaddata", str(FIXTURE_CATALOG), verbosity=0)
        count = Selo.objects.count()
        self.stdout.write(self.style.SUCCESS(f"  ✓ {count} selos carregados na BD."))

    # ── Imagens / media ────────────────────────────────────────────────────────

    def _extrair_media(self, forcar: bool) -> None:
        """Extrai o arquivo de imagens para media/selos/ se este estiver vazio (ou --forcar)."""
        if not FIXTURE_MEDIA.exists():
            self.stdout.write(
                self.style.WARNING(
                    f"⚠  Arquivo de imagens não encontrado: {FIXTURE_MEDIA}. "
                    "Cria-o com: tar -czf fixtures/media_stamps.tar.gz -C /app/media selos"
                )
            )
            return

        MEDIA_SELOS_DIR.mkdir(parents=True, exist_ok=True)
        imagens_existentes = sum(1 for _ in MEDIA_SELOS_DIR.iterdir() if _.is_file())

        if imagens_existentes > 0 and not forcar:
            self.stdout.write(
                f"  ✓ media/selos/ já tem {imagens_existentes} imagens — a saltar extracção."
            )
            return

        if imagens_existentes > 0 and forcar:
            self.stdout.write("  ⚠  --forcar activo: a re-extrair imagens.")

        self.stdout.write(f"  → A extrair imagens de {FIXTURE_MEDIA} para {settings.MEDIA_ROOT}…")
        with tarfile.open(FIXTURE_MEDIA, "r:gz") as tar:
            # Extrai para MEDIA_ROOT; o arquivo contém o directório 'selos/' internamente
            tar.extractall(path=settings.MEDIA_ROOT)

        imagens_final = sum(1 for _ in MEDIA_SELOS_DIR.iterdir() if _.is_file())
        self.stdout.write(self.style.SUCCESS(f"  ✓ {imagens_final} imagens extraídas para media/selos/."))
