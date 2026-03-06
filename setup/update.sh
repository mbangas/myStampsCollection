#!/usr/bin/env bash
# =============================================================================
#
#   myStampsCollection — Script de Actualização  v2.0
#
#   Wrapper que invoca o instalador inteligente em modo actualização.
#   Instala-se automaticamente em /usr/local/bin/mystamps-update
#   durante a instalação inicial (install.sh).
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

# -- Verificar se o directório existe ------------------------------------------
if [[ ! -d "$APP_DIR/.git" ]]; then
    echo ""
    echo "  ERRO: Directório $APP_DIR não encontrado ou não é um repositório git."
    echo "  Ajuste a variável APP_DIR neste script se instalou noutro directório."
    echo ""
    exit 1
fi

# -- Invocar o instalador inteligente em modo update ---------------------------
INSTALLER="$APP_DIR/setup/install.sh"

if [[ -f "$INSTALLER" ]]; then
    exec bash "$INSTALLER" --update --dir "$APP_DIR" "$@"
else
    # Fallback se o instalador não existir (versão antiga)
    echo ""
    echo "======================================================================"
    echo "  myStampsCollection — Actualização (fallback)"
    echo "======================================================================"
    echo ""

    echo "  --> A descarregar actualizações do GitHub..."
    git -C "$APP_DIR" pull

    echo "  --> A reconstruir imagens Docker..."
    docker compose -f "$APP_DIR/docker-compose.yml" build --pull=never

    echo "  --> A reiniciar serviços..."
    docker compose -f "$APP_DIR/docker-compose.yml" up -d

    echo ""
    echo "  Actualização concluída!"
    echo "  Aplicação disponível em: http://$(hostname -I | awk '{print $1}')"
    echo "======================================================================"
    echo ""
fi
