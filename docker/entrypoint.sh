#!/bin/sh
# =============================================================================
# Entrypoint do contentor Django – myStampsCollection
# =============================================================================
set -e

# ── Aguarda a base de dados estar pronta ─────────────────────────────────────
echo "⏳ A aguardar a base de dados PostgreSQL em ${DB_HOST}:${DB_PORT:-5432}…"

until python - <<'EOF'
import sys, os
import psycopg2
try:
    psycopg2.connect(
        dbname=os.getenv("DB_NAME", "mystamps_db"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "password"),
        host=os.getenv("DB_HOST", "db"),
        port=os.getenv("DB_PORT", "5432"),
    )
except psycopg2.OperationalError:
    sys.exit(1)
EOF
do
    echo "  – BD ainda não disponível. Nova tentativa em 2s…"
    sleep 2
done

echo "✅ Base de dados pronta."

# ── Migrações ─────────────────────────────────────────────────────────────────
echo "🔄 A aplicar migrações…"
python manage.py migrate --noinput

# ── Ficheiros estáticos ───────────────────────────────────────────────────────
echo "📦 A recolher ficheiros estáticos…"
python manage.py collectstatic --noinput --clear

# ── Symlink das imagens de selos organizadas por país ─────────────────────────
# As imagens estão em images/stamps/<ISO>/ e precisam ser acessíveis via MEDIA_ROOT.
if [ ! -e media/stamps ]; then
    echo "🔗 A criar symlink media/stamps → images/stamps…"
    ln -sfn ../images/stamps media/stamps
fi

# ── Catálogo: carrega fixtures (BD + imagens) se o volume estiver vazio ───────
# Em nova infraestrutura (volumes vazios) carrega fixtures incluídas na imagem.
# Se os volumes já tiverem dados (reinício normal) salta automaticamente.
echo "📋 A verificar/carregar catálogo de selos (fixtures)…"
python manage.py carregar_catalogo

# ── Inicia o servidor Gunicorn ────────────────────────────────────────────────
echo "🚀 A iniciar Gunicorn…"
exec gunicorn stamps_config.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers "${GUNICORN_WORKERS:-3}" \
    --timeout "${GUNICORN_TIMEOUT:-120}" \
    --log-level "${GUNICORN_LOG_LEVEL:-info}" \
    --access-logfile - \
    --error-logfile -
