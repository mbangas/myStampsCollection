#!/bin/sh
# =============================================================================
# Entrypoint do contentor Django – Selos do Mundo
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

# ── Inicia o servidor Gunicorn ────────────────────────────────────────────────
echo "🚀 A iniciar Gunicorn…"
exec gunicorn stamps_config.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers "${GUNICORN_WORKERS:-3}" \
    --timeout "${GUNICORN_TIMEOUT:-120}" \
    --log-level "${GUNICORN_LOG_LEVEL:-info}" \
    --access-logfile - \
    --error-logfile -
