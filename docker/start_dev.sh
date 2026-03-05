#!/bin/sh
# =============================================================================
# Script de arranque em modo desenvolvimento
# Executado pelo docker-compose.override.yml
# =============================================================================
set -e

echo "🔄 Migrações..."
python manage.py migrate --noinput

echo "📦 Ficheiros estáticos..."
python manage.py collectstatic --noinput

# Carrega fixtures (BD + imagens) se os volumes estiverem vazios.
# Em nova infraestrutura restaura tudo; em reinício normal salta automaticamente.
echo "📋 A verificar/carregar catálogo de selos (fixtures)…"
python manage.py carregar_catalogo

# Django arranca como processo principal (PID substituído)
echo "🚀 A iniciar servidor de desenvolvimento..."
exec python manage.py runserver 0.0.0.0:8000
