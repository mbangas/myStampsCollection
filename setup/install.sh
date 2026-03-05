#!/usr/bin/env bash
# ===============================================================================
#
#   myStampsCollection  --  Instalador Automatico  v2.0  (self-healing)
#
#   Plataforma web de gestao de colecoes de selos filatelicos
#   Django + PostgreSQL + Gunicorn + Nginx + Docker
#
#   Suporta: Debian 11/12 · Ubuntu 22.04/24.04
#   Destino: LXC em Proxmox (acabado de criar, sem Docker)
#
#   Self-healing:
#     - Detecta ambiente (LXC vs VM vs bare-metal)
#     - Aplica sysctl preventivamente em Proxmox LXC
#     - Usa network_mode: host em LXC para evitar erros de namespace
#     - Fallback automatico de storage driver (overlay2 -> vfs)
#     - Retry de build com limpeza de cache
#     - Restart automatico de contentores que falhem
#     - Idempotente: pode re-executar quantas vezes quiser
#
#   Uso:
#       bash install.sh            (como root ou com sudo)
#       sudo bash install.sh
#
# ===============================================================================

set -euo pipefail

# -- Constantes -----------------------------------------------------------------
readonly INSTALLER_VERSION="2.0"
readonly REPO_URL="https://github.com/mbangas/myStampsCollection.git"
readonly LOG="/tmp/mystamps_install_$(date +%Y%m%d_%H%M%S).log"

# Enviar trace de cada comando para o log (debug automatico)
exec 3>>"$LOG"
BASH_XTRACEFD=3
set -x

APP_DIR="/opt/mystamps"
APP_PORT="80"
DB_PASSWORD=""
SECRET_KEY=""

OS_ID=""
OS_VER=""
OS_NAME=""
SERVER_IP=""

_CURRENT_STEP="(inicializacao)"
_HEAL_ACTIONS=0
_IS_LXC=false

# -- Utilitarios de log ---------------------------------------------------------
log()  { echo "[$(date '+%H:%M:%S')] $*" >> "$LOG"; }
info() { echo "  --> $*"; log "$*"; }
warn() { echo "  [!] $*"; log "AVISO: $*"; }
heal() { echo "  [+] SELF-HEAL: $*"; log "SELF-HEAL: $*"; _HEAL_ACTIONS=$((_HEAL_ACTIONS + 1)); }
step() {
    _CURRENT_STEP="$*"
    echo ""
    echo "======================================================================"
    echo "  $*"
    echo "======================================================================"
    log "$*"
}

# -- Tratamento de erros -------------------------------------------------------
handle_error() {
    trap '' ERR
    set +eu  # desligar errexit/nounset dentro do handler
    local _ec=$?
    local _ln=${1:-"?"}

    # Escrever SEMPRE no stdout E stderr (garante visibilidade)
    echo ""
    echo "======================================================================"
    echo "  ERRO DURANTE A INSTALACAO"
    echo "======================================================================"
    echo ""
    echo "  Passo  : ${_CURRENT_STEP}"
    echo "  Linha  : ${_ln}"
    echo "  Codigo : ${_ec}"
    echo "  Log    : ${LOG}"
    echo ""
    echo "  Ultimas linhas do log:"
    echo "  ------------------------------------------------------------------"
    tail -20 "${LOG}" 2>/dev/null | sed 's/^/    /' || true
    echo ""

    echo "[$(date '+%H:%M:%S')] ERRO: passo=[${_CURRENT_STEP}] linha=${_ln} codigo=${_ec}" >> "${LOG}" 2>/dev/null || true

    if command -v whiptail &>/dev/null && { [[ -t 0 ]] || [[ -e /dev/tty ]]; }; then
        whiptail \
            --backtitle "myStampsCollection Installer  v${INSTALLER_VERSION}" \
            --title "!! ERRO NA INSTALACAO !!" \
            --msgbox \
"Ocorreu um erro durante a instalacao.

  Passo  : ${_CURRENT_STEP}
  Codigo : ${_ec}

Ultimas linhas do log:
$(tail -8 "${LOG}" 2>/dev/null | sed 's/^/  /' || true)

Log completo:
  ${LOG}

Pode re-executar (idempotente):
  sudo bash install.sh" \
            24 68 \
            </dev/tty >/dev/tty 2>/dev/null || true
    fi

    exit "${_ec}"
}

trap 'handle_error ${LINENO}' ERR

# -- Progresso no CLI -----------------------------------------------------------
progress() {
    local pct="$1"
    local msg="$2"
    local bar_len=40
    local filled=$(( pct * bar_len / 100 ))
    local empty=$(( bar_len - filled ))
    local bar=""
    for ((i=0; i<filled; i++)); do bar="${bar}#"; done
    for ((i=0; i<empty;  i++)); do bar="${bar}-"; done
    printf "\r  [%s] %3d%%  %s\n" "$bar" "$pct" "$msg"
    log "Progress ${pct}%: ${msg}"
}

# -- Verificar root -------------------------------------------------------------
check_root() {
    if [[ $EUID -ne 0 ]]; then
        echo ""
        echo "  ERRO: Execute como root ou com sudo"
        echo "  sudo bash install.sh"
        echo ""
        exit 1
    fi
}

# -- Instalar whiptail (se necessario) ------------------------------------------
ensure_whiptail() {
    if ! command -v whiptail &>/dev/null; then
        apt-get update -qq >> "$LOG" 2>&1 || true
        apt-get install -y -qq whiptail >> "$LOG" 2>&1 || true
    fi
}

# -- Detectar sistema operativo -------------------------------------------------
detect_os() {
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        OS_ID="${ID:-unknown}"
        OS_VER="${VERSION_ID:-unknown}"
        OS_NAME="${PRETTY_NAME:-${ID}}"
    else
        OS_ID="unknown"
        OS_VER="unknown"
        OS_NAME="Unknown OS"
    fi
    log "SO detectado: $OS_NAME (ID=$OS_ID  VER=$OS_VER)"
}

# -- Detectar se estamos dentro de um LXC Proxmox ------------------------------
detect_lxc() {
    if grep -qai "container=lxc" /proc/1/environ 2>/dev/null; then
        _IS_LXC=true; return
    fi
    if [[ -d /dev/lxc ]]; then
        _IS_LXC=true; return
    fi
    if command -v systemd-detect-virt &>/dev/null; then
        local virt
        virt=$(systemd-detect-virt 2>/dev/null || true)
        if [[ "$virt" == "lxc" ]]; then
            _IS_LXC=true; return
        fi
    fi
    _IS_LXC=false
}

# -- Ecra de boas-vindas --------------------------------------------------------
show_welcome() {
    local lxc_info=""
    if [[ "$_IS_LXC" == "true" ]]; then
        lxc_info="
Ambiente: Proxmox LXC (self-healing activo)"
    fi

    whiptail \
        --backtitle "myStampsCollection Installer  v${INSTALLER_VERSION}" \
        --title "myStampsCollection -- Instalador" \
        --msgbox \
"Bem-vindo ao instalador do myStampsCollection v${INSTALLER_VERSION}
Colecao de Selos Filatelicos -- Gerir, Catalogar, Trocar

Sistema detectado: ${OS_NAME}${lxc_info}

O instalador ira executar automaticamente:

 [1]  Actualizar o sistema operativo
 [2]  Instalar Docker CE
 [3]  Configurar Docker para Proxmox LXC
 [4]  Descarregar myStampsCollection do GitHub
 [5]  Configurar variaveis de ambiente (.env)
 [6]  Compilar e iniciar todos os servicos

Funcionalidades self-healing:
  - Corrige sysctl em Proxmox LXC
  - Usa network_mode: host em LXC
  - Fallback automatico de storage driver
  - Idempotente: pode re-executar

Prima OK para continuar." \
        30 64
}

# -- Confirmacao ----------------------------------------------------------------
confirm_install() {
    whiptail \
        --backtitle "myStampsCollection Installer  v${INSTALLER_VERSION}" \
        --title "myStampsCollection -- Instalador" \
        --yesno \
"Pronto para instalar myStampsCollection.

  Directorio : ${APP_DIR}
  Sistema    : ${OS_NAME}
  Log        : ${LOG}

Deseja continuar?" \
        14 64
}

# -- Perguntar configuracao -----------------------------------------------------
ask_config() {
    APP_PORT=$(whiptail \
        --backtitle "myStampsCollection Installer  v${INSTALLER_VERSION}" \
        --title "Configuracao -- Porta da Aplicacao" \
        --inputbox \
"Porta onde a aplicacao ficara disponivel.
  http://<IP-do-servidor>:<porta>

Porta (recomendado: 80):" \
        12 60 "80" 3>&1 1>&2 2>&3) || exit 0

    APP_DIR=$(whiptail \
        --backtitle "myStampsCollection Installer  v${INSTALLER_VERSION}" \
        --title "Configuracao -- Directorio" \
        --inputbox \
"Pasta onde o codigo sera instalado:

Directorio de instalacao:" \
        10 60 "/opt/mystamps" 3>&1 1>&2 2>&3) || exit 0

    DB_PASSWORD=$(whiptail \
        --backtitle "myStampsCollection Installer  v${INSTALLER_VERSION}" \
        --title "Configuracao -- Base de Dados" \
        --passwordbox \
"Password para o PostgreSQL (minimo 8 caracteres):

Password:" \
        10 60 "" 3>&1 1>&2 2>&3) || exit 0

    if [[ ${#DB_PASSWORD} -lt 8 ]]; then
        whiptail \
            --backtitle "myStampsCollection Installer  v${INSTALLER_VERSION}" \
            --title "Configuracao Invalida" \
            --msgbox "Password muito curta (minimo 8 caracteres).
Re-execute o instalador." \
            8 54
        exit 1
    fi
}

# ==============================================================================
#   PASSO 1: ACTUALIZAR SISTEMA
# ==============================================================================
step_update_system() {
    step "PASSO 1/6: Actualizar sistema operativo"
    export DEBIAN_FRONTEND=noninteractive
    info "A executar apt-get update..."
    apt-get update -qq                                      >> "$LOG" 2>&1
    info "A actualizar pacotes instalados..."
    apt-get upgrade -y -qq                                  >> "$LOG" 2>&1
    info "A instalar dependencias basicas..."
    apt-get install -y -qq \
        curl wget git ca-certificates gnupg \
        lsb-release apt-transport-https \
        software-properties-common \
        openssl python3                                     >> "$LOG" 2>&1
    info "Sistema actualizado com sucesso."
}

# ==============================================================================
#   PASSO 2: INSTALAR DOCKER CE
# ==============================================================================
step_install_docker() {
    step "PASSO 2/6: Instalar Docker CE"

    if command -v docker &>/dev/null; then
        info "Docker ja esta instalado: $(docker --version)"
        if docker compose version &>/dev/null; then
            info "Docker Compose disponivel: $(docker compose version)"
        else
            heal "Docker Compose plugin em falta -- a instalar"
            apt-get install -y -qq docker-compose-plugin    >> "$LOG" 2>&1
        fi
        # Garantir que esta a correr
        systemctl start docker >> "$LOG" 2>&1 || true
        _wait_for_docker
        return 0
    fi

    info "A remover versoes antigas do Docker..."
    apt-get remove -y -qq \
        docker docker-engine docker.io containerd runc \
        2>/dev/null >> "$LOG" 2>&1 || true

    info "A configurar repositorio oficial Docker..."
    install -m 0755 -d /etc/apt/keyrings

    if [[ "$OS_ID" == "ubuntu" ]]; then
        curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
            | gpg --dearmor -o /etc/apt/keyrings/docker.gpg >> "$LOG" 2>&1
        chmod a+r /etc/apt/keyrings/docker.gpg
        echo \
          "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
           https://download.docker.com/linux/ubuntu \
           $(lsb_release -cs) stable" \
          > /etc/apt/sources.list.d/docker.list
    else
        curl -fsSL https://download.docker.com/linux/debian/gpg \
            | gpg --dearmor -o /etc/apt/keyrings/docker.gpg >> "$LOG" 2>&1
        chmod a+r /etc/apt/keyrings/docker.gpg
        echo \
          "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
           https://download.docker.com/linux/debian \
           $(lsb_release -cs) stable" \
          > /etc/apt/sources.list.d/docker.list
    fi

    info "A instalar Docker CE e plugin Compose..."
    apt-get update -qq                                      >> "$LOG" 2>&1
    apt-get install -y -qq \
        docker-ce docker-ce-cli containerd.io \
        docker-buildx-plugin docker-compose-plugin         >> "$LOG" 2>&1

    systemctl enable docker                                 >> "$LOG" 2>&1
    systemctl start docker                                  >> "$LOG" 2>&1 || true

    _wait_for_docker

    info "Docker instalado: $(docker --version)"
    info "Docker Compose: $(docker compose version)"
}

# -- Aguardar Docker operacional (nunca falha fatalmente) ----------------------
_wait_for_docker() {
    local waited=0
    while ! docker info &>/dev/null 2>&1; do
        sleep 2; waited=$((waited + 2))
        if (( waited >= 60 )); then
            warn "Docker nao respondeu em 60s -- a prosseguir mesmo assim"
            return 0
        fi
    done
    if [[ $waited -gt 0 ]]; then
        info "Docker operacional apos ${waited}s."
    fi
}

# ==============================================================================
#   PASSO 3: CONFIGURAR DOCKER PARA PROXMOX LXC (self-healing)
# ==============================================================================
step_configure_docker_lxc() {
    step "PASSO 3/6: Configurar Docker para Proxmox LXC"

    if [[ "$_IS_LXC" == "true" ]]; then
        info "Ambiente: Proxmox LXC detectado"
        _heal_sysctl
    else
        info "Ambiente: VM ou bare-metal (configuracao LXC nao necessaria)"
    fi

    # Testar se Docker funciona SEM parar/reiniciar -- so testa
    _test_docker_quick
}

# -- Aplicar sysctl preventivamente -------------------------------------------
_heal_sysctl() {
    local current_val
    current_val=$(sysctl -n net.ipv4.ip_unprivileged_port_start 2>/dev/null || echo "?")
    log "sysctl ip_unprivileged_port_start actual: ${current_val}"

    if [[ "$current_val" != "0" ]]; then
        heal "A definir net.ipv4.ip_unprivileged_port_start=0"
        sysctl -w net.ipv4.ip_unprivileged_port_start=0 >> "$LOG" 2>&1 || {
            warn "sysctl nao aceite pelo kernel -- nao e fatal"
            log "AVISO: sysctl falhou (kernel bloqueou)"
        }
    else
        info "sysctl ja correctamente definido (valor=0)."
    fi

    # Persistir para sobreviver a reboot
    echo "net.ipv4.ip_unprivileged_port_start=0" \
        > /etc/sysctl.d/99-docker-lxc.conf 2>/dev/null || true
    log "sysctl persistido em /etc/sysctl.d/99-docker-lxc.conf"
}

# -- Teste rapido: Docker funciona? Nao reinicia nada. -------------------------
_test_docker_quick() {
    info "A testar se Docker consegue arrancar contentores..."

    # Garantir Docker activo
    if ! docker info &>/dev/null 2>&1; then
        systemctl start docker >> "$LOG" 2>&1 || true
        _wait_for_docker
    fi

    local test_out
    # Tentar sem pull primeiro
    test_out=$(docker run --rm --pull=never hello-world 2>&1) || true

    # Se imagem nao existe localmente, descarregar
    if echo "$test_out" | grep -qi "Unable to find image\|No such image"; then
        info "A descarregar imagem de teste..."
        docker pull hello-world >> "$LOG" 2>&1 || true
        test_out=$(docker run --rm hello-world 2>&1) || true
    fi

    # Analisar resultado
    if echo "$test_out" | grep -q "Hello from Docker"; then
        info "Teste Docker: OK -- contentores funcionam."
        docker rmi hello-world >> "$LOG" 2>&1 || true
        return 0
    fi

    # -- Erro: MS_PRIVATE (nesting nao activo) --------------------------------
    if echo "$test_out" | grep -q "MS_PRIVATE\|remount-private"; then
        heal "MS_PRIVATE detectado -- a tentar fallback para vfs"
        _fallback_to_vfs
        test_out=$(docker run --rm hello-world 2>&1) || true
        if echo "$test_out" | grep -q "Hello from Docker"; then
            info "Teste apos fallback vfs: OK"
            docker rmi hello-world >> "$LOG" 2>&1 || true
            return 0
        fi
        _fail_nesting "$test_out"
    fi

    # -- Erro: sysctl (nao fatal -- o network_mode:host resolve isto) ---------
    if echo "$test_out" | grep -q "ip_unprivileged_port_start"; then
        warn "Erro sysctl no teste -- network_mode:host ira resolver isto."
        log "sysctl erro detectado no teste: ${test_out}"
        docker rmi hello-world >> "$LOG" 2>&1 || true
        return 0
    fi

    # -- Erro: runc/shim generico ---------------------------------------------
    if echo "$test_out" | grep -qi "failed to create shim\|runc create failed"; then
        heal "Erro runc/shim -- a tentar fallback vfs"
        _fallback_to_vfs
        test_out=$(docker run --rm hello-world 2>&1) || true
        if echo "$test_out" | grep -q "Hello from Docker"; then
            info "Teste apos fallback vfs: OK"
            docker rmi hello-world >> "$LOG" 2>&1 || true
            return 0
        fi
        # Se o erro e sysctl, o network_mode:host resolve
        if echo "$test_out" | grep -q "ip_unprivileged_port_start"; then
            warn "Erro sysctl persistente -- network_mode:host ira resolver."
            docker rmi hello-world >> "$LOG" 2>&1 || true
            return 0
        fi
        _fail_docker "$test_out"
    fi

    # Qualquer outro caso: nao fatal, prosseguir
    warn "Teste Docker com resultado inesperado -- a prosseguir."
    log "Teste Docker output: ${test_out}"
    docker rmi hello-world >> "$LOG" 2>&1 || true
}

# -- Fallback: mudar storage driver para vfs -----------------------------------
_fallback_to_vfs() {
    warn "overlay2 nao funciona -- a mudar para vfs..."
    systemctl stop docker docker.socket 2>/dev/null         >> "$LOG" 2>&1 || true
    systemctl stop containerd 2>/dev/null                   >> "$LOG" 2>&1 || true
    sleep 3
    rm -rf /var/lib/docker/* /var/lib/containerd/*
    mkdir -p /etc/docker
    printf '{\n  "storage-driver": "vfs"\n}\n' > /etc/docker/daemon.json
    systemctl start containerd                              >> "$LOG" 2>&1 || true
    sleep 3
    systemctl start docker                                  >> "$LOG" 2>&1 || true
    sleep 5
    _wait_for_docker
    local driver
    driver=$(docker info --format '{{.Driver}}' 2>/dev/null || echo "?")
    heal "Storage driver alterado para: ${driver}"
}

# -- Erro fatal: nesting -------------------------------------------------------
_fail_nesting() {
    local detail="${1:-}"
    log "ERRO nesting: ${detail}"

    echo "" >&2
    echo "======================================================================" >&2
    echo "  ERRO: Docker nao pode arrancar contentores neste LXC" >&2
    echo "======================================================================" >&2
    echo "" >&2
    echo "  Causa: o LXC nao tem a opcao 'nesting' activa." >&2
    echo "" >&2
    echo "  SOLUCAO -- executar NO HOST PROXMOX:" >&2
    echo "" >&2
    echo "    1. pct list" >&2
    echo "    2. pct set XXX --features nesting=1,keyctl=1" >&2
    echo "    3. pct stop XXX && pct start XXX" >&2
    echo "    4. Re-executar: bash install.sh" >&2
    echo "" >&2

    if command -v whiptail &>/dev/null; then
        whiptail \
            --backtitle "myStampsCollection Installer  v${INSTALLER_VERSION}" \
            --title "Configuracao Proxmox Necessaria" \
            --msgbox \
"Docker nao consegue correr contentores.

SOLUCAO -- no HOST Proxmox:

  1. pct list
  2. pct set XXX --features nesting=1,keyctl=1
  3. pct stop XXX && pct start XXX
  4. Re-executar: bash install.sh" \
            16 60 \
            </dev/tty >/dev/tty 2>/dev/null || true
    fi
    exit 1
}

# -- Erro fatal: Docker -------------------------------------------------------
_fail_docker() {
    local detail="${1:-}"
    log "ERRO Docker fatal: ${detail}"
    echo "" >&2
    echo "  ERRO: Docker nao funciona. Detalhe: ${detail}" >&2
    echo "  Log: ${LOG}" >&2
    exit 1
}

# ==============================================================================
#   PASSO 4: CLONAR REPOSITORIO
# ==============================================================================
step_clone_repo() {
    step "PASSO 4/6: Descarregar myStampsCollection do GitHub"

    mkdir -p "$APP_DIR"

    if [[ -d "$APP_DIR/.git" ]]; then
        info "Repositorio ja existe -- a actualizar..."
        git -C "$APP_DIR" pull                              >> "$LOG" 2>&1
    else
        info "A clonar repositorio de ${REPO_URL}..."
        git clone "$REPO_URL" "$APP_DIR"                    >> "$LOG" 2>&1
    fi
    info "Repositorio disponivel em: $APP_DIR"
}

# ==============================================================================
#   PASSO 5: CRIAR .env + docker-compose.yml ADAPTADO
# ==============================================================================
step_create_env() {
    step "PASSO 5/6: Configurar ambiente"

    # ── .env ─────────────────────────────────────────────────────────────────
    if [[ -f "$APP_DIR/.env" ]]; then
        info "Ficheiro .env ja existe -- preservado."
        log ".env existente preservado"
    else
        SECRET_KEY=$(openssl rand -base64 64 | tr -dc 'a-zA-Z0-9!@#%^&*(-_=+)' | head -c 50)
        log "SECRET_KEY gerada."

        SERVER_IP=$(hostname -I 2>/dev/null | awk '{print $1}') || true
        if [[ -z "$SERVER_IP" ]]; then SERVER_IP="127.0.0.1"; fi

        local allowed_hosts="localhost,127.0.0.1,${SERVER_IP}"

        cat > "$APP_DIR/.env" << ENV_CONTENT
# =============================================================================
# myStampsCollection -- Configuracao de Producao
# Gerado pelo instalador em $(date)
# NAO partilhe este ficheiro -- contem credenciais
# =============================================================================

# -- Django -------------------------------------------------------------------
SECRET_KEY=${SECRET_KEY}
DEBUG=False
ALLOWED_HOSTS=${allowed_hosts}
CSRF_TRUSTED_ORIGINS=

# -- Base de Dados PostgreSQL -------------------------------------------------
DB_NAME=mystamps_db
DB_USER=stamps_user
DB_PASSWORD=${DB_PASSWORD}
DB_HOST=db
DB_PORT=5432

# -- Gunicorn -----------------------------------------------------------------
GUNICORN_WORKERS=3
GUNICORN_TIMEOUT=120
GUNICORN_LOG_LEVEL=info
ENV_CONTENT

        chmod 600 "$APP_DIR/.env"
        info "Ficheiro .env criado."
        info "ALLOWED_HOSTS: ${allowed_hosts}"
    fi

    # ── docker-compose.yml adaptado para LXC ─────────────────────────────────
    # Em Proxmox LXC, o runc nao consegue escrever sysctl no namespace de rede.
    # Usar network_mode: host elimina completamente este problema (abordagem
    # usada tambem pelo myLineage).
    if [[ "$_IS_LXC" == "true" ]]; then
        info "Proxmox LXC: a gerar docker-compose.yml com network_mode: host"
        _generate_compose_host
    else
        info "VM/bare-metal: a usar docker-compose.yml do repositorio (bridge)"
    fi

    # ── Ajustar porta se diferente de 80 ─────────────────────────────────────
    _configure_port
}

# -- Gerar docker-compose.yml com network_mode: host ---------------------------
# Abordagem inspirada pelo myLineage: em LXC Proxmox, network_mode: host
# elimina TODOS os erros de sysctl/namespace porque os contentores partilham
# a stack de rede do host -- nao e criado novo namespace.
_generate_compose_host() {
    local compose_file="$APP_DIR/docker-compose.yml"

    # Guardar backup do original
    if [[ -f "$compose_file" ]]; then
        cp "$compose_file" "${compose_file}.original"
        log "Backup: ${compose_file}.original"
    fi

    cat > "$compose_file" << 'COMPOSE_CONTENT'
# =============================================================================
# myStampsCollection -- docker-compose.yml (Proxmox LXC)
# network_mode: host -- evita erros de sysctl/namespace em LXC
# Gerado automaticamente pelo instalador v2.0
# =============================================================================

services:

  db:
    image: postgres:16-alpine
    container_name: stamps_db
    restart: unless-stopped
    network_mode: host
    volumes:
      - postgres_data:/var/lib/postgresql/data
    env_file:
      - .env
    environment:
      POSTGRES_DB: ${DB_NAME:-mystamps_db}
      POSTGRES_USER: ${DB_USER:-postgres}
      POSTGRES_PASSWORD: ${DB_PASSWORD:-password}
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER:-postgres} -d ${DB_NAME:-mystamps_db} -h 127.0.0.1"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 10s

  web:
    build:
      context: .
      dockerfile: Dockerfile
      target: runtime
    container_name: stamps_web
    restart: unless-stopped
    network_mode: host
    depends_on:
      db:
        condition: service_healthy
    env_file:
      - .env
    environment:
      DB_HOST: 127.0.0.1
    volumes:
      - media_data:/app/media
      - static_data:/app/staticfiles

  nginx:
    image: nginx:1.27-alpine
    container_name: stamps_nginx
    restart: unless-stopped
    network_mode: host
    depends_on:
      - web
    volumes:
      - ./docker/nginx/default.conf:/etc/nginx/conf.d/default.conf:ro
      - media_data:/app/media:ro
      - static_data:/app/staticfiles:ro

volumes:
  postgres_data:
  media_data:
  static_data:
COMPOSE_CONTENT

    # Ajustar .env: DB_HOST deve ser 127.0.0.1 em modo host
    if [[ -f "$APP_DIR/.env" ]]; then
        sed -i 's/^DB_HOST=.*/DB_HOST=127.0.0.1/' "$APP_DIR/.env"
        log ".env actualizado: DB_HOST=127.0.0.1"
    fi

    # Ajustar Nginx upstream para 127.0.0.1 em vez do nome do servico
    local nginx_conf="$APP_DIR/docker/nginx/default.conf"
    if [[ -f "$nginx_conf" ]]; then
        sed -i 's/server web:8000;/server 127.0.0.1:8000;/' "$nginx_conf"
        log "Nginx upstream: 127.0.0.1:8000"
    fi

    info "docker-compose.yml gerado com network_mode: host"
}

# -- Ajustar porta se nao for 80 -----------------------------------------------
_configure_port() {
    if [[ "$APP_PORT" == "80" ]]; then
        log "Porta padrao 80 -- sem alteracoes."
        return 0
    fi

    info "A ajustar porta para ${APP_PORT}..."

    local nginx_conf="$APP_DIR/docker/nginx/default.conf"
    if [[ -f "$nginx_conf" ]]; then
        sed -i "s/listen 80;/listen ${APP_PORT};/" "$nginx_conf"
        log "Nginx listen: ${APP_PORT}"
    fi

    # Se estiver a usar bridge (nao LXC), ajustar mapeamento de portas
    local compose_file="$APP_DIR/docker-compose.yml"
    if [[ -f "$compose_file" ]] && grep -q '"80:80"' "$compose_file"; then
        sed -i "s/\"80:80\"/\"${APP_PORT}:${APP_PORT}\"/" "$compose_file"
        log "Compose port mapping: ${APP_PORT}"
    fi
}

# ==============================================================================
#   PASSO 6: BUILD E ARRANQUE (com self-healing)
# ==============================================================================
step_build_and_start() {
    step "PASSO 6/6: Compilar imagens e iniciar servicos"

    info "ATENCAO: A compilacao pode demorar varios minutos."
    echo ""

    cd "$APP_DIR"

    # -- Build com retry -------------------------------------------------------
    local build_ok=false
    for attempt in 1 2 3; do
        info "Build: tentativa ${attempt}/3..."
        if docker compose -f docker-compose.yml build 2>&1 | tee -a "$LOG"; then
            build_ok=true
            break
        fi
        warn "Build falhou na tentativa ${attempt}/3"
        if (( attempt < 3 )); then
            heal "A limpar cache Docker e a re-tentar..."
            docker builder prune -f >> "$LOG" 2>&1 || true
            sleep 5
        fi
    done

    if [[ "$build_ok" != "true" ]]; then
        echo "  ERRO: Build falhou apos 3 tentativas." >&2
        echo "  Verifique a ligacao a Internet e o espaco em disco." >&2
        echo "  Log: ${LOG}" >&2
        exit 1
    fi

    echo ""
    info "Build concluido. A iniciar servicos..."

    # -- Arrancar servicos com self-healing ------------------------------------
    _start_services
}

# -- Iniciar servicos -----------------------------------------------------------
_start_services() {
    cd "$APP_DIR"

    # Parar servicos anteriores se existirem
    docker compose -f docker-compose.yml down 2>/dev/null   >> "$LOG" 2>&1 || true

    local start_out
    start_out=$(docker compose -f docker-compose.yml up -d 2>&1) || true
    echo "$start_out" | tee -a "$LOG"

    # Se erro de sysctl mesmo com network_mode:host (muito raro), avisar
    if echo "$start_out" | grep -q "ip_unprivileged_port_start"; then
        heal "Erro sysctl no arranque -- a re-aplicar sysctl e re-tentar"
        _heal_sysctl
        docker compose -f docker-compose.yml down 2>/dev/null >> "$LOG" 2>&1 || true
        start_out=$(docker compose -f docker-compose.yml up -d 2>&1) || true
        echo "$start_out" | tee -a "$LOG"
    fi

    # Se erro de runc/shim
    if echo "$start_out" | grep -qi "failed to create shim\|runc create failed"; then
        heal "Erro runc no arranque -- a tentar fallback vfs"
        _fallback_to_vfs
        docker compose -f docker-compose.yml down 2>/dev/null >> "$LOG" 2>&1 || true
        start_out=$(docker compose -f docker-compose.yml up -d 2>&1) || true
        echo "$start_out" | tee -a "$LOG"
    fi

    sleep 5
    echo ""
    info "Estado dos contentores:"
    docker compose -f docker-compose.yml ps 2>&1 | tee -a "$LOG"
    echo ""

    # Self-heal: reiniciar contentores que nao estao running
    for svc in db web nginx; do
        local cstatus
        cstatus=$(docker inspect --format='{{.State.Status}}' "stamps_${svc}" 2>/dev/null || echo "missing")
        if [[ "$cstatus" != "running" ]]; then
            heal "A reiniciar stamps_${svc} (estado: ${cstatus})"
            docker start "stamps_${svc}" >> "$LOG" 2>&1 || true
            sleep 3
        fi
    done

    info "Servicos iniciados."
}

# -- Verificar saude da aplicacao -----------------------------------------------
step_health_check() {
    info "A aguardar que a aplicacao fique disponivel..."
    local waited=0

    while true; do
        if curl -sf "http://localhost:${APP_PORT}" > /dev/null 2>&1; then
            break
        fi

        # Self-heal: se web morreu (ex: BD nao pronta), reiniciar
        local web_status
        web_status=$(docker inspect --format='{{.State.Status}}' stamps_web 2>/dev/null || echo "unknown")
        if [[ "$web_status" == "exited" || "$web_status" == "dead" ]]; then
            heal "stamps_web parou -- a reiniciar"
            docker start stamps_web >> "$LOG" 2>&1 || true
        fi

        sleep 5; waited=$((waited + 5))
        printf "\r  Aguardar... %ds" "$waited"

        if (( waited >= 180 )); then
            echo ""
            warn "Tempo esgotado (180s)"
            info "A aplicacao pode ainda estar a iniciar (migrações, fixtures)."
            info "Verifique: docker logs stamps_web -f"
            return 0
        fi
    done

    if [[ $waited -gt 0 ]]; then echo ""; fi
    info "Aplicacao disponivel e a responder!"
}

# -- Instalar script de actualizacao -------------------------------------------
_install_update_script() {
    local src="$APP_DIR/setup/update.sh"
    local dest="/usr/local/bin/mystamps-update"

    if [[ -f "$src" ]]; then
        cp "$src" "$dest"
        chmod +x "$dest"
        sed -i "s|APP_DIR=\"/opt/mystamps\"|APP_DIR=\"${APP_DIR}\"|" "$dest"
        info "Script de actualizacao: mystamps-update"
    fi
}

# ==============================================================================
#   PROGRAMA PRINCIPAL
# ==============================================================================

: > "$LOG"
log "myStampsCollection Instalador v${INSTALLER_VERSION} (self-healing) -- $(date)"
log "Repositorio: $REPO_URL"

check_root
ensure_whiptail
detect_os
detect_lxc

if [[ "$_IS_LXC" == "true" ]]; then
    log "Ambiente: Proxmox LXC detectado"
else
    log "Ambiente: VM / bare-metal"
fi

show_welcome

if ! confirm_install; then
    whiptail \
        --backtitle "myStampsCollection Installer  v${INSTALLER_VERSION}" \
        --title "Instalacao Cancelada" \
        --msgbox "Instalacao cancelada.

Pode re-executar a qualquer momento:
  sudo bash install.sh" \
        8 50
    exit 0
fi

ask_config

log "Config: APP_DIR=$APP_DIR  PORT=$APP_PORT  LXC=$_IS_LXC"

echo ""
echo "======================================================================"
echo "  myStampsCollection -- Instalacao em curso (v${INSTALLER_VERSION})"
echo "  Inclui self-healing automatico para Proxmox LXC"
echo "  ATENCAO: Este processo e demorado. Por favor aguarde."
echo "======================================================================"
echo ""

progress  5  "A actualizar sistema operativo..."
step_update_system

progress 20  "A instalar Docker CE..."
step_install_docker

progress 30  "A configurar Docker para Proxmox LXC..."
step_configure_docker_lxc

progress 45  "A descarregar repositorio..."
step_clone_repo

progress 55  "A configurar ambiente (.env + docker-compose)..."
step_create_env

progress 65  "A compilar e iniciar servicos (pode demorar)..."
step_build_and_start

progress 90  "A verificar disponibilidade da aplicacao..."
step_health_check

progress 95  "A instalar script de actualizacao..."
_install_update_script

progress 100 "Instalacao concluida!"

# Desactivar trap
trap '' ERR

# -- Resumo final ---------------------------------------------------------------
_FINAL_IP=$(hostname -I 2>/dev/null | awk '{print $1}') || true
if [[ -z "$_FINAL_IP" ]]; then _FINAL_IP="127.0.0.1"; fi
_SUMMARY="/root/mystamps-access.txt"

cat > "$_SUMMARY" << SUMMARY_EOF
======================================================================
  myStampsCollection -- RESUMO DE ACESSO
  Instalado em: $(date)
  Versao instalador: ${INSTALLER_VERSION}
======================================================================

  Aplicacao  -->  http://${_FINAL_IP}:${APP_PORT}
  Admin      -->  http://${_FINAL_IP}:${APP_PORT}/admin/

  Primeiro acesso:
    1. Aceder a http://${_FINAL_IP}:${APP_PORT}
    2. Registar uma conta em "Registar"
    3. Criar superutilizador:
       docker exec -it stamps_web python manage.py createsuperuser

  COMANDOS UTEIS:
    Actualizar:     mystamps-update
    Ver logs web:   docker logs stamps_web -f
    Ver logs db:    docker logs stamps_db -f
    Ver logs nginx: docker logs stamps_nginx -f
    Parar:          docker compose -f ${APP_DIR}/docker-compose.yml down
    Reiniciar:      docker compose -f ${APP_DIR}/docker-compose.yml restart
    Log instalacao: ${LOG}
SUMMARY_EOF

if (( _HEAL_ACTIONS > 0 )); then
    echo "    Self-heal:      ${_HEAL_ACTIONS} accoes de auto-reparacao" >> "$_SUMMARY"
fi

echo "======================================================================" >> "$_SUMMARY"

# Imprimir no terminal
echo ""
echo "======================================================================"
echo "  myStampsCollection -- INSTALACAO CONCLUIDA!"
echo "======================================================================"
echo ""
echo "  Aplicacao  -->  http://${_FINAL_IP}:${APP_PORT}"
echo "  Admin      -->  http://${_FINAL_IP}:${APP_PORT}/admin/"
echo ""
echo "  Primeiro acesso:"
echo "    1. Abrir http://${_FINAL_IP}:${APP_PORT} no browser"
echo "    2. Registar uma conta"
echo "    3. Criar superutilizador:"
echo "       docker exec -it stamps_web python manage.py createsuperuser"
echo ""
if (( _HEAL_ACTIONS > 0 )); then
    echo "  Self-healing: ${_HEAL_ACTIONS} accoes de auto-reparacao aplicadas"
    echo "  (Detalhes no log: ${LOG})"
    echo ""
fi
echo "  Para actualizar: mystamps-update"
echo "  Resumo guardado: ${_SUMMARY}"
echo ""
echo "======================================================================"
echo ""

log "=== Instalacao concluida (self-heal: ${_HEAL_ACTIONS}) ==="
exit 0
