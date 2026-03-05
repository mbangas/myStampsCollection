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
#     - Corrige automaticamente storage driver (overlay2 / vfs)
#     - Corrige sysctl ip_unprivileged_port_start em Proxmox LXC
#     - Fallback para network_mode: host como ultimo recurso
#     - Retry de build com limpeza de cache
#     - Restart automatico de contentores que falhem a arrancar
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
    local _ec=$?
    local _ln=${1:-"?"}

    echo "" >&2
    echo "======================================================================" >&2
    echo "  ERRO DURANTE A INSTALACAO" >&2
    echo "======================================================================" >&2
    echo "" >&2
    echo "  Passo  : ${_CURRENT_STEP}" >&2
    echo "  Linha  : ${_ln}" >&2
    echo "  Codigo : ${_ec}" >&2
    echo "  Log    : ${LOG}" >&2
    echo "" >&2
    echo "  Ultimas linhas do log:" >&2
    echo "  ------------------------------------------------------------------" >&2
    tail -20 "${LOG}" 2>/dev/null | sed 's/^/    /' >&2 || true
    echo "" >&2

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

Verifique:
  - Ligacao a Internet activa
  - Espaco em disco suficiente
  - Docker em execucao:
    systemctl status docker

Pode re-executar (o instalador e idempotente):
  sudo bash install.sh" \
            28 68 \
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
        info "A instalar whiptail..."
        apt-get update -qq >> "$LOG" 2>&1 && apt-get install -y -qq whiptail >> "$LOG" 2>&1
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
is_proxmox_lxc() {
    if grep -qai "container=lxc" /proc/1/environ 2>/dev/null; then
        return 0
    fi
    if [[ -d /dev/lxc ]]; then
        return 0
    fi
    if command -v systemd-detect-virt &>/dev/null; then
        local virt
        virt=$(systemd-detect-virt 2>/dev/null || true)
        [[ "$virt" == "lxc" ]] && return 0
    fi
    return 1
}

# -- Ecra de boas-vindas --------------------------------------------------------
show_welcome() {
    whiptail \
        --backtitle "myStampsCollection Installer  v${INSTALLER_VERSION}" \
        --title "myStampsCollection -- Instalador" \
        --msgbox \
"Bem-vindo ao instalador do myStampsCollection v${INSTALLER_VERSION}
Colecao de Selos Filatelicos -- Gerir, Catalogar, Trocar

Sistema detectado: ${OS_NAME}

O instalador ira executar automaticamente:

 [1]  Actualizar o sistema operativo
 [2]  Instalar Docker CE (com self-healing para LXC)
 [3]  Descarregar myStampsCollection do GitHub
 [4]  Configurar variaveis de ambiente (.env)
 [5]  Compilar as imagens Docker e iniciar servicos

Funcionalidades self-healing incluidas:
  - Corrige automaticamente storage driver (overlay2/vfs)
  - Corrige sysctl em Proxmox LXC
  - Detecta e resolve erros de nesting
  - Idempotente: pode re-executar com seguranca

Prima OK para continuar." \
        28 64
}

# -- Confirmacao ----------------------------------------------------------------
confirm_install() {
    whiptail \
        --backtitle "myStampsCollection Installer  v${INSTALLER_VERSION}" \
        --title "myStampsCollection -- Instalador" \
        --yesno \
"Pronto para instalar myStampsCollection no seu servidor.

  Directorio de instalacao : ${APP_DIR}
  Sistema operativo        : ${OS_NAME}
  Log de instalacao        : ${LOG}

ATENCAO: A instalacao e demorada (5-20 minutos).
O progresso sera mostrado no terminal.

Deseja continuar?" \
        16 64
}

# -- Perguntar configuracao -----------------------------------------------------
ask_config() {
    APP_PORT=$(whiptail \
        --backtitle "myStampsCollection Installer  v${INSTALLER_VERSION}" \
        --title "Configuracao -- Porta da Aplicacao" \
        --inputbox \
"Porta onde o myStampsCollection ficara disponivel.

Depois da instalacao, a aplicacao estara
acessivel em:
  http://<IP-do-servidor>:<porta>

Porta (recomendado: 80):" \
        14 60 "80" 3>&1 1>&2 2>&3) || exit 0

    APP_DIR=$(whiptail \
        --backtitle "myStampsCollection Installer  v${INSTALLER_VERSION}" \
        --title "Configuracao -- Directorio de Instalacao" \
        --inputbox \
"Pasta onde o codigo da aplicacao sera instalado.
(Git clone do repositorio)

Directorio de instalacao:" \
        10 60 "/opt/mystamps" 3>&1 1>&2 2>&3) || exit 0

    DB_PASSWORD=$(whiptail \
        --backtitle "myStampsCollection Installer  v${INSTALLER_VERSION}" \
        --title "Configuracao -- Base de Dados PostgreSQL" \
        --passwordbox \
"Password para a base de dados PostgreSQL.

Use uma password segura (minimo 8 caracteres).
Esta password e guardada no ficheiro .env.

Password da base de dados:" \
        13 60 "" 3>&1 1>&2 2>&3) || exit 0

    if [[ ${#DB_PASSWORD} -lt 8 ]]; then
        whiptail \
            --backtitle "myStampsCollection Installer  v${INSTALLER_VERSION}" \
            --title "Configuracao Invalida" \
            --msgbox "A password deve ter pelo menos 8 caracteres.

Por favor reinicie o instalador e use
uma password mais longa." \
            10 54
        exit 1
    fi
}

# ==============================================================================
#   PASSO 1: ACTUALIZAR SISTEMA OPERATIVO
# ==============================================================================
step_update_system() {
    step "PASSO 1/5: Actualizar sistema operativo"
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
#   PASSO 2: INSTALAR DOCKER CE (com self-healing)
# ==============================================================================
step_install_docker() {
    step "PASSO 2/5: Instalar Docker CE"

    # -- 2a. Se Docker ja instalado, verificar compose e prosseguir -----------
    if command -v docker &>/dev/null; then
        info "Docker ja esta instalado: $(docker --version)"
        if docker compose version &>/dev/null; then
            info "Docker Compose disponivel: $(docker compose version)"
        else
            heal "Docker Compose plugin em falta -- a instalar"
            apt-get install -y -qq docker-compose-plugin    >> "$LOG" 2>&1
        fi
        _ensure_docker_running
        return 0
    fi

    # -- 2b. Remover versoes antigas ------------------------------------------
    info "A remover versoes antigas do Docker..."
    apt-get remove -y -qq \
        docker docker-engine docker.io containerd runc \
        2>/dev/null >> "$LOG" 2>&1 || true

    # -- 2c. Configurar repositorio oficial Docker ----------------------------
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

    # -- 2d. Instalar Docker CE e Compose -------------------------------------
    info "A instalar Docker CE e plugin Compose..."
    apt-get update -qq                                      >> "$LOG" 2>&1
    apt-get install -y -qq \
        docker-ce docker-ce-cli containerd.io \
        docker-buildx-plugin docker-compose-plugin         >> "$LOG" 2>&1

    info "A iniciar servico Docker..."
    systemctl enable docker                                 >> "$LOG" 2>&1

    _ensure_docker_running

    info "Docker instalado: $(docker --version)"
    info "Docker Compose: $(docker compose version)"
}

# -- Garantir que o Docker daemon esta activo e a responder --------------------
_ensure_docker_running() {
    systemctl start docker >> "$LOG" 2>&1 || true
    local waited=0
    while ! docker info &>/dev/null; do
        sleep 2; waited=$((waited + 2))
        if (( waited >= 60 )); then
            log "ERRO: Docker nao disponivel apos 60s"
            return 1
        fi
    done
    [[ $waited -gt 0 ]] && info "Docker operacional apos ${waited}s."
}

# ==============================================================================
#   SELF-HEALING: STORAGE DRIVER + SYSCTL (Proxmox LXC)
# ==============================================================================
#
# Em Proxmox LXC existem dois problemas comuns:
#
#   1. overlay2 pode falhar com "MS_PRIVATE: permission denied"
#      quando nesting nao esta activo -> fallback automatico para vfs
#
#   2. runc tenta escrever net.ipv4.ip_unprivileged_port_start no namespace
#      de rede do contentor; o kernel do LXC bloqueia essa escrita
#      -> definir o sysctl no host LXC ANTES de arrancar contentores
#
# Estrategia:
#   - Detecta o ambiente (LXC vs bare-metal vs VM)
#   - Aplica o sysctl preventivamente
#   - Testa se Docker consegue criar contentores
#   - Se falha: muda storage driver, reinicia, re-testa
#   - Se tudo falha: mostra instrucoes claras para o utilizador
#
step_heal_docker_lxc() {
    step "SELF-HEALING: Configurar Docker para Proxmox LXC"

    local in_lxc=false
    if is_proxmox_lxc; then
        in_lxc=true
        info "Ambiente detectado: Proxmox LXC"
    else
        info "Ambiente detectado: VM ou bare-metal (nao e LXC)"
    fi

    # -- Correcao preventiva do sysctl (apenas em LXC) -------------------------
    if [[ "$in_lxc" == "true" ]]; then
        _heal_sysctl
    fi

    # -- Garantir Docker limpo e operacional -----------------------------------
    _heal_storage_driver

    # -- Teste final: criar um contentor real ----------------------------------
    _test_docker_container "$in_lxc"

    info "Docker completamente operacional."
}

# -- Corrigir sysctl net.ipv4.ip_unprivileged_port_start -----------------------
_heal_sysctl() {
    local current_val
    current_val=$(sysctl -n net.ipv4.ip_unprivileged_port_start 2>/dev/null || echo "?")
    log "net.ipv4.ip_unprivileged_port_start actual: ${current_val}"

    if [[ "$current_val" != "0" ]]; then
        heal "A definir net.ipv4.ip_unprivileged_port_start=0"
        if sysctl -w net.ipv4.ip_unprivileged_port_start=0 >> "$LOG" 2>&1; then
            info "sysctl aplicado com sucesso."
        else
            warn "Nao foi possivel definir sysctl (kernel pode nao permitir)."
            warn "Se os contentores falharem, configure no host Proxmox:"
            warn "  Editar /etc/pve/lxc/<ID>.conf"
            warn "  Adicionar: lxc.sysctl.net.ipv4.ip_unprivileged_port_start = 0"
            log "AVISO: sysctl falhou -- pode necessitar configuracao no host Proxmox"
        fi
    else
        info "sysctl ja correctamente definido (valor=0)."
    fi

    # Persistir para sobreviver a reboot
    echo "net.ipv4.ip_unprivileged_port_start=0" \
        > /etc/sysctl.d/99-docker-lxc.conf 2>/dev/null || true
    log "sysctl persistido em /etc/sysctl.d/99-docker-lxc.conf"
}

# -- Configurar storage driver -------------------------------------------------
_heal_storage_driver() {
    # Parar Docker para reconfigurar
    systemctl stop docker docker.socket 2>/dev/null         >> "$LOG" 2>&1 || true
    systemctl stop containerd 2>/dev/null                   >> "$LOG" 2>&1 || true
    sleep 3

    # Se ja existem contentores de instalacao anterior, preservar dados
    if [[ -d /var/lib/docker/containers ]] && \
       [[ $(find /var/lib/docker/containers -maxdepth 1 -type d 2>/dev/null | wc -l) -gt 1 ]]; then
        info "Dados Docker existentes detectados -- preservando."
        log "Dados Docker existentes preservados"
    else
        info "A limpar dados anteriores do Docker..."
        rm -rf /var/lib/docker/* /var/lib/containerd/*
        log "Dados anteriores removidos"
    fi

    # Remover daemon.json -- deixar overlay2 por omissao
    rm -f /etc/docker/daemon.json
    log "daemon.json removido -- Docker vai usar overlay2 por omissao"

    # Reiniciar Docker
    info "A reiniciar Docker..."
    systemctl start containerd                              >> "$LOG" 2>&1
    sleep 3
    systemctl start docker                                  >> "$LOG" 2>&1
    sleep 5

    _ensure_docker_running

    local driver
    driver=$(docker info --format '{{.Driver}}' 2>/dev/null || echo "?")
    info "Storage driver activo: ${driver}"
    log "Storage driver: ${driver}"
}

# -- Testar se Docker consegue criar contentores --------------------------------
_test_docker_container() {
    local in_lxc="${1:-false}"

    info "A testar se Docker consegue arrancar contentores..."

    local test_out
    test_out=$(docker run --rm --pull=never hello-world 2>&1) || true

    # Se imagem nao existe, descarregar
    if echo "$test_out" | grep -qi "Unable to find image\|No such image"; then
        info "A descarregar imagem de teste (hello-world)..."
        docker pull hello-world >> "$LOG" 2>&1 || true
        test_out=$(docker run --rm hello-world 2>&1) || true
    fi

    # -- Self-heal para erros conhecidos ---------------------------------------

    # Erro 1: MS_PRIVATE (overlay2 sem nesting)
    if echo "$test_out" | grep -q "MS_PRIVATE\|remount-private"; then
        heal "MS_PRIVATE detectado -- a mudar storage driver para vfs"
        _fallback_to_vfs
        test_out=$(docker run --rm hello-world 2>&1) || true
        if echo "$test_out" | grep -q "MS_PRIVATE\|remount-private"; then
            _fail_nesting "$test_out"
        fi
    fi

    # Erro 2: sysctl ip_unprivileged_port_start
    if echo "$test_out" | grep -q "ip_unprivileged_port_start"; then
        heal "Erro sysctl detectado no teste -- a tentar correcao"
        _heal_sysctl
        test_out=$(docker run --rm hello-world 2>&1) || true
        if echo "$test_out" | grep -q "ip_unprivileged_port_start"; then
            warn "sysctl continua a falhar -- os contentores podem funcionar sem este sysctl."
            log "AVISO: sysctl ainda falha apos self-heal"
        fi
    fi

    # Erro 3: qualquer outro erro de runc/shim
    if echo "$test_out" | grep -qi "failed to create shim\|runc create failed"; then
        heal "Erro runc/shim detectado -- a tentar fallback vfs"
        _fallback_to_vfs
        test_out=$(docker run --rm hello-world 2>&1) || true
        if echo "$test_out" | grep -qi "failed to create shim\|runc create failed"; then
            _fail_docker "$test_out"
        fi
    fi

    if echo "$test_out" | grep -q "Hello from Docker"; then
        info "Teste hello-world: OK"
    else
        log "Teste hello-world output: ${test_out}"
        warn "Output inesperado do teste -- a prosseguir."
    fi

    # Limpar imagem de teste
    docker rmi hello-world 2>/dev/null >> "$LOG" 2>&1 || true
}

# -- Fallback: mudar storage driver para vfs -----------------------------------
_fallback_to_vfs() {
    warn "overlay2 nao funciona -- a mudar para vfs..."
    systemctl stop docker docker.socket containerd 2>/dev/null >> "$LOG" 2>&1 || true
    sleep 3
    rm -rf /var/lib/docker/* /var/lib/containerd/*
    mkdir -p /etc/docker
    printf '{\n  "storage-driver": "vfs"\n}\n' > /etc/docker/daemon.json
    systemctl start containerd >> "$LOG" 2>&1; sleep 3
    systemctl start docker     >> "$LOG" 2>&1; sleep 5

    _ensure_docker_running

    local driver
    driver=$(docker info --format '{{.Driver}}' 2>/dev/null || echo "?")
    heal "Storage driver alterado para: ${driver}"
}

# -- Erro fatal: nesting nao activo -------------------------------------------
_fail_nesting() {
    local detail="${1:-}"
    log "ERRO nesting: ${detail}"

    echo "" >&2
    echo "======================================================================" >&2
    echo "  ERRO: Docker nao pode arrancar contentores neste LXC" >&2
    echo "======================================================================" >&2
    echo "" >&2
    echo "  Causa: o LXC Proxmox nao tem a opcao 'nesting' activa." >&2
    echo "  O self-healing tentou corrigir automaticamente mas nao conseguiu." >&2
    echo "" >&2
    echo "  SOLUCAO -- executar NO HOST PROXMOX:" >&2
    echo "" >&2
    echo "    1. Ver o ID deste LXC:" >&2
    echo "         pct list" >&2
    echo "" >&2
    echo "    2. Activar nesting (substituir XXX pelo ID do LXC):" >&2
    echo "         pct set XXX --features nesting=1,keyctl=1" >&2
    echo "" >&2
    echo "    3. (Opcional) Permitir sysctl:" >&2
    echo "         echo 'lxc.sysctl.net.ipv4.ip_unprivileged_port_start = 0' \\" >&2
    echo "           >> /etc/pve/lxc/XXX.conf" >&2
    echo "" >&2
    echo "    4. Reiniciar o LXC:" >&2
    echo "         pct stop XXX && pct start XXX" >&2
    echo "" >&2
    echo "    5. Re-executar o instalador:" >&2
    echo "         bash install.sh" >&2
    echo "" >&2

    whiptail \
        --backtitle "myStampsCollection Installer  v${INSTALLER_VERSION}" \
        --title "Configuracao Proxmox Necessaria" \
        --msgbox \
"O Docker nao consegue correr contentores.

O self-healing tentou corrigir mas o LXC
continua a bloquear.

SOLUCAO -- no HOST Proxmox:

  1. pct list
  2. pct set XXX --features nesting=1,keyctl=1
  3. (Opcional) Editar /etc/pve/lxc/XXX.conf
     Adicionar:
       lxc.sysctl.net.ipv4.ip_unprivileged_port_start = 0
  4. pct stop XXX && pct start XXX
  5. Re-executar: bash install.sh" \
        24 64 \
        </dev/tty >/dev/tty 2>/dev/null || true

    exit 1
}

# -- Erro fatal generico Docker ------------------------------------------------
_fail_docker() {
    local detail="${1:-}"
    log "ERRO Docker fatal: ${detail}"

    echo "" >&2
    echo "======================================================================" >&2
    echo "  ERRO: Docker nao funciona correctamente" >&2
    echo "======================================================================" >&2
    echo "  O self-healing nao conseguiu resolver o problema." >&2
    echo "  Detalhe: ${detail}" >&2
    echo "  Log: ${LOG}" >&2
    echo "" >&2

    exit 1
}

# ==============================================================================
#   PASSO 3: CLONAR REPOSITORIO
# ==============================================================================
step_clone_repo() {
    step "PASSO 3/5: Descarregar myStampsCollection do GitHub"

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
#   PASSO 4: CRIAR .env
# ==============================================================================
step_create_env() {
    step "PASSO 4/5: Configurar variaveis de ambiente"

    # Se .env ja existe, preservar (idempotente)
    if [[ -f "$APP_DIR/.env" ]]; then
        info "Ficheiro .env ja existe -- preservado."
        info "Para recriar, apague $APP_DIR/.env e re-execute o instalador."
        log ".env existente preservado"
        return 0
    fi

    SECRET_KEY=$(openssl rand -base64 64 | tr -dc 'a-zA-Z0-9!@#%^&*(-_=+)' | head -c 50)
    log "SECRET_KEY gerada automaticamente."

    SERVER_IP=$(hostname -I 2>/dev/null | awk '{print $1}') || true
    [[ -z "$SERVER_IP" ]] && SERVER_IP="127.0.0.1"

    local allowed_hosts="localhost,127.0.0.1,${SERVER_IP}"

    cat > "$APP_DIR/.env" << ENV_CONTENT
# =============================================================================
# myStampsCollection -- Configuracao de Producao
# Gerado automaticamente pelo instalador em $(date)
#
# NAO partilhe este ficheiro -- contem credenciais sensiveis
# =============================================================================

# -- Django -------------------------------------------------------------------
SECRET_KEY=${SECRET_KEY}
DEBUG=False
ALLOWED_HOSTS=${allowed_hosts}
CSRF_TRUSTED_ORIGINS=

# -- Base de Dados PostgreSQL --------------------------------------------------
DB_NAME=mystamps_db
DB_USER=stamps_user
DB_PASSWORD=${DB_PASSWORD}
DB_HOST=db
DB_PORT=5432

# -- Gunicorn ------------------------------------------------------------------
GUNICORN_WORKERS=3
GUNICORN_TIMEOUT=120
GUNICORN_LOG_LEVEL=info
ENV_CONTENT

    chmod 600 "$APP_DIR/.env"
    info "Ficheiro .env criado em $APP_DIR/.env"
    info "ALLOWED_HOSTS: ${allowed_hosts}"
}

# -- Ajustar porta no Nginx e docker-compose -----------------------------------
step_configure_port() {
    local nginx_conf="$APP_DIR/docker/nginx/default.conf"
    local compose_file="$APP_DIR/docker-compose.yml"

    if [[ "$APP_PORT" == "80" ]]; then
        log "Porta padrao 80 -- sem alteracoes necessarias."
        return 0
    fi

    info "A ajustar porta para ${APP_PORT}..."

    if [[ -f "$nginx_conf" ]]; then
        sed -i "s/listen 80;/listen ${APP_PORT};/" "$nginx_conf"
        log "Nginx configurado para porta ${APP_PORT}"
    fi

    if [[ -f "$compose_file" ]]; then
        sed -i "s/\"80:80\"/\"${APP_PORT}:${APP_PORT}\"/" "$compose_file"
        log "docker-compose.yml actualizado para porta ${APP_PORT}"
    fi
}

# ==============================================================================
#   PASSO 5: BUILD, ARRANQUE COM SELF-HEALING
# ==============================================================================
step_build_and_start() {
    step "PASSO 5/5: Compilar imagens Docker e iniciar servicos"

    info "ATENCAO: A compilacao da imagem pode demorar varios minutos."
    echo ""

    cd "$APP_DIR"

    # -- Build com retry -------------------------------------------------------
    local build_ok=false
    local max_retries=3

    for attempt in $(seq 1 $max_retries); do
        info "Tentativa de build ${attempt}/${max_retries}..."
        if docker compose -f docker-compose.yml build 2>&1 | tee -a "$LOG"; then
            build_ok=true
            break
        else
            warn "Build falhou na tentativa ${attempt}/${max_retries}"
            if (( attempt < max_retries )); then
                heal "A limpar cache e a re-tentar build..."
                docker builder prune -f >> "$LOG" 2>&1 || true
                sleep 5
            fi
        fi
    done

    if [[ "$build_ok" != "true" ]]; then
        log "ERRO: Build falhou apos ${max_retries} tentativas"
        echo "  ERRO: Build falhou. Verifique a ligacao a Internet e o espaco em disco." >&2
        exit 1
    fi

    echo ""
    info "Build concluido. A iniciar servicos..."

    # -- Arranque com self-healing ---------------------------------------------
    _start_services_with_healing
}

# -- Iniciar servicos com auto-reparacao ----------------------------------------
_start_services_with_healing() {
    cd "$APP_DIR"

    # Parar servicos anteriores (idempotente)
    docker compose -f docker-compose.yml down 2>/dev/null   >> "$LOG" 2>&1 || true

    # Primeira tentativa de arranque
    local start_out
    start_out=$(docker compose -f docker-compose.yml up -d 2>&1) || true
    echo "$start_out" >> "$LOG"
    echo "$start_out"

    # -- Self-heal: erro de sysctl no arranque ---------------------------------
    if echo "$start_out" | grep -q "ip_unprivileged_port_start"; then
        heal "Erro sysctl detectado no arranque -- a aplicar correcao"
        _heal_sysctl

        docker compose -f docker-compose.yml down 2>/dev/null >> "$LOG" 2>&1 || true
        start_out=$(docker compose -f docker-compose.yml up -d 2>&1) || true
        echo "$start_out" >> "$LOG"

        if echo "$start_out" | grep -q "ip_unprivileged_port_start"; then
            warn "sysctl continua a falhar -- a tentar network_mode: host"
            _fallback_network_host
            return
        fi
    fi

    # -- Self-heal: erro de runc/shim no arranque ------------------------------
    if echo "$start_out" | grep -qi "failed to create shim\|runc create failed"; then
        heal "Erro runc detectado no arranque -- a tentar fallback vfs"
        _fallback_to_vfs
        docker compose -f docker-compose.yml down 2>/dev/null >> "$LOG" 2>&1 || true
        start_out=$(docker compose -f docker-compose.yml up -d 2>&1) || true
        echo "$start_out" >> "$LOG"

        # Se ainda falha com sysctl, tentar network_mode: host
        if echo "$start_out" | grep -q "ip_unprivileged_port_start"; then
            warn "Erro persiste apos vfs -- a tentar network_mode: host"
            _fallback_network_host
            return
        fi
    fi

    sleep 5
    info "Estado dos contentores apos arranque:"
    docker compose -f docker-compose.yml ps 2>&1 | tee -a "$LOG"
    echo ""

    # -- Self-heal: contentores que nao estao running --------------------------
    for svc in db web nginx; do
        local status
        status=$(docker inspect --format='{{.State.Status}}' "stamps_${svc}" 2>/dev/null || echo "missing")
        if [[ "$status" != "running" ]]; then
            heal "A reiniciar stamps_${svc} (estado: ${status})"
            docker start "stamps_${svc}" >> "$LOG" 2>&1 || true
            sleep 3
        fi
    done

    info "Servicos iniciados."
}

# -- Ultimo recurso: network_mode: host ----------------------------------------
# Elimina TODOS os problemas de namespace de rede (sysctl, portas, etc.)
_fallback_network_host() {
    heal "A reconfigurar docker-compose com network_mode: host (ultimo recurso)"

    local compose_file="$APP_DIR/docker-compose.yml"

    # Guardar backup
    cp "$compose_file" "${compose_file}.bak.$(date +%s)"

    cat > "$compose_file" << 'COMPOSE_HOST'
# =============================================================================
# myStampsCollection -- docker-compose.yml (network_mode: host)
# Gerado automaticamente pelo self-healing do instalador.
# Contentores partilham a rede do host para evitar erros de sysctl/namespace.
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
COMPOSE_HOST

    # Ajustar nginx upstream para localhost
    local nginx_conf="$APP_DIR/docker/nginx/default.conf"
    if [[ -f "$nginx_conf" ]]; then
        sed -i 's/server web:8000;/server 127.0.0.1:8000;/' "$nginx_conf"
        log "Nginx upstream alterado para 127.0.0.1:8000"
    fi

    info "docker-compose.yml recriado com network_mode: host"

    docker compose -f "$compose_file" down 2>/dev/null      >> "$LOG" 2>&1 || true
    docker compose -f "$compose_file" up -d 2>&1 | tee -a "$LOG"

    sleep 5
    info "Estado dos contentores (network_mode: host):"
    docker compose -f "$compose_file" ps 2>&1 | tee -a "$LOG"
}

# -- Verificar saude dos servicos -----------------------------------------------
step_health_check() {
    info "A aguardar que todos os servicos fiquem operacionais..."
    local waited=0

    while true; do
        if curl -sf "http://localhost:${APP_PORT}" > /dev/null 2>&1; then
            break
        fi

        local web_status
        web_status=$(docker inspect --format='{{.State.Status}}' stamps_web 2>/dev/null || echo "unknown")

        # Self-heal: reiniciar contentor web se morreu
        if [[ "$web_status" == "exited" || "$web_status" == "dead" ]]; then
            local logs_tail
            logs_tail=$(docker logs stamps_web --tail 10 2>&1 || true)
            log "stamps_web ${web_status}: ${logs_tail}"

            if echo "$logs_tail" | grep -qi "could not connect\|connection refused\|psycopg2"; then
                heal "BD ainda nao esta pronta -- a reiniciar stamps_web"
                docker start stamps_web >> "$LOG" 2>&1 || true
            fi
        fi

        sleep 5; waited=$((waited + 5))
        printf "\r  Aguardar servicos... %ds" "$waited"

        if (( waited >= 120 )); then
            echo ""
            warn "Tempo esgotado (120s) -- servicos podem ainda estar a iniciar"
            info "Verifique com: docker logs stamps_web -f"
            info "A aplicacao estara disponivel em: http://${SERVER_IP}:${APP_PORT}"
            return 0
        fi
    done

    [[ $waited -gt 0 ]] && echo ""
    info "Aplicacao disponivel e a responder."
}

# -- Instalar script de actualizacao -------------------------------------------
_install_update_script() {
    local src="$APP_DIR/setup/update.sh"
    local dest="/usr/local/bin/mystamps-update"

    if [[ -f "$src" ]]; then
        cp "$src" "$dest"
        chmod +x "$dest"
        sed -i "s|APP_DIR=\"/opt/mystamps\"|APP_DIR=\"${APP_DIR}\"|" "$dest"
        log "Script de actualizacao instalado em: ${dest}"
        info "Script de actualizacao: mystamps-update"
    else
        log "AVISO: $src nao encontrado"
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
show_welcome

if ! confirm_install; then
    whiptail \
        --backtitle "myStampsCollection Installer  v${INSTALLER_VERSION}" \
        --title "Instalacao Cancelada" \
        --msgbox "Instalacao cancelada pelo utilizador.

Pode re-executar o instalador a qualquer momento:
  sudo bash install.sh" \
        10 54
    exit 0
fi

ask_config

log "Configuracao: APP_DIR=$APP_DIR  PORT=$APP_PORT"

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

progress 35  "Self-healing: a configurar Docker para Proxmox LXC..."
step_heal_docker_lxc

progress 50  "A descarregar repositorio..."
step_clone_repo

progress 60  "A criar configuracao (.env)..."
step_create_env

progress 65  "A configurar porta ${APP_PORT}..."
step_configure_port

progress 70  "A compilar e iniciar servicos (pode demorar)..."
step_build_and_start

progress 90  "A verificar disponibilidade da aplicacao..."
step_health_check

progress 95  "A instalar script de actualizacao..."
_install_update_script

progress 100 "Instalacao concluida!"

# Desactivar trap de erros
trap '' ERR

# -- Resumo final ---------------------------------------------------------------
_FINAL_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
[[ -z "$_FINAL_IP" ]] && _FINAL_IP="127.0.0.1"
_SUMMARY="/root/mystamps-access.txt"

printf '======================================================================\n'       > "$_SUMMARY"
printf '  myStampsCollection -- RESUMO DE ACESSO\n'                                   >> "$_SUMMARY"
printf '  Instalado em: %s\n' "$(date)"                                                >> "$_SUMMARY"
printf '  Versao instalador: %s\n' "$INSTALLER_VERSION"                                >> "$_SUMMARY"
printf '======================================================================\n'       >> "$_SUMMARY"
printf '\n'                                                                             >> "$_SUMMARY"
printf '  Aplicacao  -->  http://%s:%s\n'  "$_FINAL_IP" "$APP_PORT"                   >> "$_SUMMARY"
printf '\n'                                                                             >> "$_SUMMARY"
printf '  COMANDOS UTEIS:\n'                                                           >> "$_SUMMARY"
printf '    Actualizar:     mystamps-update\n'                                         >> "$_SUMMARY"
printf '    Ver logs web:   docker logs stamps_web -f\n'                               >> "$_SUMMARY"
printf '    Ver logs db:    docker logs stamps_db -f\n'                                >> "$_SUMMARY"
printf '    Ver logs nginx: docker logs stamps_nginx -f\n'                             >> "$_SUMMARY"
printf '    Parar:          docker compose -f %s/docker-compose.yml down\n' "$APP_DIR" >> "$_SUMMARY"
printf '    Reiniciar:      docker compose -f %s/docker-compose.yml restart\n' "$APP_DIR" >> "$_SUMMARY"
printf '    Log instalacao: %s\n' "$LOG"                                               >> "$_SUMMARY"
if (( _HEAL_ACTIONS > 0 )); then
    printf '    Self-heal:      %d accoes de auto-reparacao aplicadas\n' "$_HEAL_ACTIONS" >> "$_SUMMARY"
fi
printf '\n'                                                                             >> "$_SUMMARY"
printf '======================================================================\n'       >> "$_SUMMARY"

printf '\n'
printf '======================================================================\n'
printf '  myStampsCollection -- INSTALACAO CONCLUIDA!\n'
printf '======================================================================\n'
printf '\n'
printf '  Aplicacao  -->  http://%s:%s\n'  "$_FINAL_IP" "$APP_PORT"
printf '\n'
if (( _HEAL_ACTIONS > 0 )); then
    printf '  Self-healing: %d accoes de auto-reparacao aplicadas\n' "$_HEAL_ACTIONS"
    printf '  (Consulte o log para detalhes: %s)\n' "$LOG"
    printf '\n'
fi
printf '  Para actualizar no futuro: mystamps-update\n'
printf '  (Resumo guardado em: %s)\n' "$_SUMMARY"
printf '\n'
printf '======================================================================\n'
printf '\n'

log "=== Instalacao concluida em $(date) (self-heal actions: ${_HEAL_ACTIONS}) ==="
exit 0
