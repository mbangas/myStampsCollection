#!/usr/bin/env bash
# =============================================================================
#
#   myStampsCollection -- Script de Actualizacao  v1.0
#
#   Instala-se automaticamente em /usr/local/bin/mystamps-update
#   durante a instalacao inicial (install.sh).
#
#   Uso:
#       mystamps-update          (como root ou com sudo)
#       sudo mystamps-update
#
# =============================================================================

set -euo pipefail

APP_DIR="/opt/mystamps"

# -- Verificar root -------------------------------------------------------------
if [[ $EUID -ne 0 ]]; then
    echo ""
    echo "  ERRO: Execute como root ou com sudo"
    echo "  sudo mystamps-update"
    echo ""
    exit 1
fi

# -- Verificar se o directorio existe ------------------------------------------
if [[ ! -d "$APP_DIR/.git" ]]; then
    echo ""
    echo "  ERRO: Directorio $APP_DIR nao encontrado ou nao e um repositorio git."
    echo "  Ajuste a variavel APP_DIR neste script se instalou noutro directorio."
    echo ""
    exit 1
fi

echo ""
echo "======================================================================"
echo "  myStampsCollection -- Actualizacao"
echo "======================================================================"
echo ""

echo "  --> A descarregar actualizacoes do GitHub..."
git -C "$APP_DIR" pull

echo "  --> A reconstruir imagens Docker..."
docker compose -f "$APP_DIR/docker-compose.yml" build

echo "  --> A reiniciar servicos..."
docker compose -f "$APP_DIR/docker-compose.yml" up -d

echo ""
echo "  Actualizacao concluida!"
echo "  Aplicacao disponivel em: http://$(hostname -I | awk '{print $1}')"
echo "======================================================================"
echo ""
