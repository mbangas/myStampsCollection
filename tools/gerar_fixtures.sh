#!/bin/sh
# =============================================================================
# Gera as fixtures do catálogo (BD + arquivo de imagens) a partir do estado
# actual do contentor em execução.
#
# Corre sempre que o catálogo for actualizado com novos selos/imagens,
# para que a próxima build Docker inclua os dados mais recentes.
#
# Pré-requisito: docker compose up (contentor stamps_web a correr)
#
# Uso:
#   sh tools/gerar_fixtures.sh
# =============================================================================
set -e

FIXTURES_DIR="$(dirname "$0")/../fixtures"
mkdir -p "$FIXTURES_DIR"

echo "📋 A exportar fixtures da BD (catalog.json)…"
docker compose exec web python manage.py dumpdata catalog --indent 2 \
    --output /app/fixtures/catalog.json
echo "  ✓ fixtures/catalog.json actualizado."

echo "🗜  A criar arquivo de imagens (media_stamps.tar.gz)…"
docker compose exec web sh -c \
    "tar -czf /tmp/media_stamps.tar.gz -C /app/media selos"
docker cp stamps_web:/tmp/media_stamps.tar.gz "$FIXTURES_DIR/media_stamps.tar.gz"
echo "  ✓ fixtures/media_stamps.tar.gz actualizado."

echo ""
echo "✅ Fixtures prontas em fixtures/."
echo "   Faz commit dos ficheiros e rebuild da imagem para os incluir:"
echo "     git add fixtures/ && git commit -m 'chore: actualizar fixtures do catálogo'"
echo "     docker compose build"
