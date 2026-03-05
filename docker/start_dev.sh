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

echo "📋 Importar catálogo Portugal (StampData)..."
python -u tools/importar_selos_portugal.py --pular-se-populado

# Lança em background: imagens PT → catálogo ES → imagens ES
echo "⏳ A lançar carregamento de dados em background (PT imagens → ES catálogo → ES imagens)..."
sh /app/docker/carregar_dados_bg.sh &

# Django arranca como processo principal (PID substituído)
echo "🚀 A iniciar servidor de desenvolvimento..."
exec python manage.py runserver 0.0.0.0:8000
