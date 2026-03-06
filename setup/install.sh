#!/usr/bin/env bash
# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║                                                                         ║
# ║   📮  myStampsCollection  —  Instalador Inteligente  v3.0               ║
# ║                                                                         ║
# ║   Plataforma web de gestão de coleções de selos filatélicos             ║
# ║   Django · PostgreSQL · Gunicorn · Nginx · Docker                       ║
# ║                                                                         ║
# ║   ✦ Detecta automaticamente: INSTALAÇÃO nova ou ACTUALIZAÇÃO            ║
# ║   ✦ Progresso visual com cores, spinners e barra animada               ║
# ║   ✦ Self-healing para Proxmox LXC (nesting, sysctl, vfs)               ║
# ║   ✦ Verificação completa de saúde no final                              ║
# ║   ✦ Idempotente: pode re-executar quantas vezes quiser                  ║
# ║                                                                         ║
# ║   Uso:                                                                  ║
# ║       curl -fsSL <repo>/setup/install.sh | sudo bash                    ║
# ║       sudo bash install.sh                                              ║
# ║       sudo bash install.sh --update       (forçar modo actualização)    ║
# ║       sudo bash install.sh --install      (forçar modo instalação)      ║
# ║                                                                         ║
# ║   Suporta: Debian 11/12 · Ubuntu 22.04/24.04                           ║
# ║   Destino: LXC em Proxmox (acabado de criar, sem Docker)               ║
# ║                                                                         ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

set -euo pipefail

# ─── Constantes ────────────────────────────────────────────────────────────────
readonly INSTALLER_VERSION="3.0"
readonly REPO_URL="https://github.com/mbangas/myStampsCollection.git"
readonly LOG="/tmp/mystamps_install_$(date +%Y%m%d_%H%M%S).log"
readonly APP_NAME="myStampsCollection"

# Trace para o log
exec 3>>"$LOG"
BASH_XTRACEFD=3
set -x

# ─── Variáveis de estado ──────────────────────────────────────────────────────
APP_DIR="/opt/mystamps"
APP_PORT="80"
DB_PASSWORD=""
SECRET_KEY=""
OS_ID=""
OS_VER=""
OS_NAME=""
SERVER_IP=""

_CURRENT_STEP="(inicialização)"
_HEAL_ACTIONS=0
_IS_LXC=false
_MODE=""              # "install" ou "update"
_FORCE_MODE=""        # argumento --install ou --update
_TOTAL_STEPS=0
_CURRENT_STEP_NUM=0
_START_TIME=$(date +%s)

# ─── Cores e Símbolos ─────────────────────────────────────────────────────────
if [[ -t 1 ]] && command -v tput &>/dev/null && [[ $(tput colors 2>/dev/null || echo 0) -ge 8 ]]; then
    readonly C_RESET='\033[0m'
    readonly C_BOLD='\033[1m'
    readonly C_DIM='\033[2m'
    readonly C_RED='\033[0;31m'
    readonly C_GREEN='\033[0;32m'
    readonly C_YELLOW='\033[0;33m'
    readonly C_BLUE='\033[0;34m'
    readonly C_MAGENTA='\033[0;35m'
    readonly C_CYAN='\033[0;36m'
    readonly C_WHITE='\033[1;37m'
    readonly C_BG_GREEN='\033[42m'
    readonly C_BG_RED='\033[41m'
    readonly SYM_OK='✅'
    readonly SYM_FAIL='❌'
    readonly SYM_WARN='⚠️ '
    readonly SYM_ARROW='➜'
    readonly SYM_HEAL='🔧'
    readonly SYM_STAMP='📮'
    readonly SYM_ROCKET='🚀'
    readonly SYM_LINK='🔗'
    readonly SYM_KEY='🔑'
    readonly SYM_DOCKER='🐳'
    readonly SYM_GEAR='⚙️ '
    readonly SYM_CHECK='✔'
    readonly SYM_CROSS='✘'
    readonly SYM_DOT='●'
    readonly SYM_STAR='★'
    readonly SYM_CLOCK='⏱ '
else
    readonly C_RESET='' C_BOLD='' C_DIM='' C_RED='' C_GREEN='' C_YELLOW=''
    readonly C_BLUE='' C_MAGENTA='' C_CYAN='' C_WHITE=''
    readonly C_BG_GREEN='' C_BG_RED=''
    readonly SYM_OK='[OK]' SYM_FAIL='[FAIL]' SYM_WARN='[!]'
    readonly SYM_ARROW='-->' SYM_HEAL='[FIX]' SYM_STAMP='[*]'
    readonly SYM_ROCKET='[>]' SYM_LINK='[>]' SYM_KEY='[K]'
    readonly SYM_DOCKER='[D]' SYM_GEAR='[G]'
    readonly SYM_CHECK='[v]' SYM_CROSS='[x]' SYM_DOT='*'
    readonly SYM_STAR='*' SYM_CLOCK='[T]'
fi

# Spinner frames
readonly SPINNER_FRAMES=('⠋' '⠙' '⠹' '⠸' '⠼' '⠴' '⠦' '⠧' '⠇' '⠏')
readonly SPINNER_PLAIN=('|' '/' '-' '\')

# ─── Funções de UI ────────────────────────────────────────────────────────────

_line() {
    printf "  ${C_DIM}"
    printf '%*s' 66 '' | tr ' ' '─'
    printf "${C_RESET}\n"
}

_banner() {
    local mode_label mode_color
    if [[ "$_MODE" == "update" ]]; then
        mode_label="ACTUALIZAÇÃO"
        mode_color="${C_CYAN}"
    else
        mode_label="INSTALAÇÃO"
        mode_color="${C_GREEN}"
    fi

    echo ""
    printf "${C_BOLD}${C_BLUE}"
    echo "  ╔════════════════════════════════════════════════════════════════╗"
    echo "  ║                                                              ║"
    printf "  ║   ${SYM_STAMP}  ${C_WHITE}myStampsCollection${C_BLUE}  —  v${INSTALLER_VERSION}                     ║\n"
    printf "  ║      ${mode_color}${C_BOLD}${mode_label}${C_BLUE}                                      ║\n"
    echo "  ║                                                              ║"
    echo "  ║  Colecção de Selos — Gerir, Catalogar, Trocar               ║"
    echo "  ║                                                              ║"
    echo "  ╚════════════════════════════════════════════════════════════════╝"
    printf "${C_RESET}\n"
}

_step_header() {
    local title="$1"
    local icon="${2:-${SYM_GEAR}}"
    _CURRENT_STEP_NUM=$((_CURRENT_STEP_NUM + 1))
    _CURRENT_STEP="$title"

    echo ""
    printf "  ${C_BOLD}${C_BLUE}${icon}  PASSO ${_CURRENT_STEP_NUM}/${_TOTAL_STEPS}: ${C_WHITE}${title}${C_RESET}\n"
    _line
}

_info() {
    printf "  ${C_DIM}${SYM_ARROW}${C_RESET}  %s\n" "$*"
    log "$*"
}

_ok() {
    printf "  ${C_GREEN}${SYM_OK}${C_RESET}  ${C_GREEN}%s${C_RESET}\n" "$*"
    log "OK: $*"
}

_warn() {
    printf "  ${C_YELLOW}${SYM_WARN}${C_RESET} ${C_YELLOW}%s${C_RESET}\n" "$*"
    log "AVISO: $*"
}

_fail() {
    printf "  ${C_RED}${SYM_FAIL}${C_RESET}  ${C_RED}%s${C_RESET}\n" "$*"
    log "ERRO: $*"
}

_heal() {
    printf "  ${C_MAGENTA}${SYM_HEAL}${C_RESET}  ${C_MAGENTA}SELF-HEAL: %s${C_RESET}\n" "$*"
    log "SELF-HEAL: $*"
    _HEAL_ACTIONS=$((_HEAL_ACTIONS + 1))
}

# Spinner animado — uso: _spin "mensagem" comando args...
_spin() {
    local msg="$1"; shift
    local pid frames frame_count i

    "$@" >> "$LOG" 2>&1 &
    pid=$!

    if [[ -n "${C_BOLD}" ]]; then
        frames=("${SPINNER_FRAMES[@]}")
    else
        frames=("${SPINNER_PLAIN[@]}")
    fi
    frame_count=${#frames[@]}
    i=0

    while kill -0 "$pid" 2>/dev/null; do
        printf "\r  ${C_CYAN}${frames[$((i % frame_count))]}${C_RESET}  %s" "$msg"
        sleep 0.1
        i=$((i + 1))
    done

    wait "$pid"
    local rc=$?

    if [[ $rc -eq 0 ]]; then
        printf "\r  ${C_GREEN}${SYM_CHECK}${C_RESET}  %s\n" "$msg"
    else
        printf "\r  ${C_RED}${SYM_CROSS}${C_RESET}  %s ${C_RED}(erro: ${rc})${C_RESET}\n" "$msg"
    fi
    return $rc
}

# Barra de progresso global
_progress_bar() {
    local pct="$1"
    local msg="$2"
    local bar_width=40
    local filled=$(( pct * bar_width / 100 ))
    local empty=$(( bar_width - filled ))
    local bar=""

    for ((i=0; i<filled; i++)); do bar="${bar}█"; done
    for ((i=0; i<empty;  i++)); do bar="${bar}░"; done

    local elapsed=$(( $(date +%s) - _START_TIME ))
    local mins=$(( elapsed / 60 ))
    local secs=$(( elapsed % 60 ))

    printf "\r  ${C_BOLD}[${C_GREEN}%s${C_RESET}${C_BOLD}]${C_RESET} ${C_WHITE}%3d%%${C_RESET}  ${C_DIM}%s${C_RESET}  ${C_DIM}${SYM_CLOCK}%02d:%02d${C_RESET}" \
        "$bar" "$pct" "$msg" "$mins" "$secs"
    echo ""
    log "Progresso ${pct}%: ${msg} (${mins}m${secs}s)"
}

# ─── Logging ───────────────────────────────────────────────────────────────────
log() { echo "[$(date '+%H:%M:%S')] $*" >> "$LOG"; }

# ─── Tratamento de Erros ──────────────────────────────────────────────────────
handle_error() {
    trap '' ERR
    set +eu
    local _ec=$?
    local _ln=${1:-"?"}

    echo ""
    printf "  ${C_BG_RED}${C_WHITE}${C_BOLD}                                                            ${C_RESET}\n"
    printf "  ${C_BG_RED}${C_WHITE}${C_BOLD}    ${SYM_FAIL}  ERRO DURANTE A %s                          ${C_RESET}\n" "${_MODE^^:-OPERAÇÃO}"
    printf "  ${C_BG_RED}${C_WHITE}${C_BOLD}                                                            ${C_RESET}\n"
    echo ""
    printf "  ${C_RED}Passo${C_RESET}  : ${_CURRENT_STEP}\n"
    printf "  ${C_RED}Linha${C_RESET}  : ${_ln}\n"
    printf "  ${C_RED}Código${C_RESET} : ${_ec}\n"
    printf "  ${C_RED}Log${C_RESET}    : ${LOG}\n"
    echo ""
    printf "  ${C_DIM}Últimas linhas do log:${C_RESET}\n"
    _line
    tail -15 "${LOG}" 2>/dev/null | sed 's/^/    /' || true
    echo ""
    _line
    echo ""
    printf "  ${C_YELLOW}Idempotente — pode re-executar:${C_RESET}\n"
    printf "  ${C_WHITE}  sudo bash install.sh${C_RESET}\n"
    echo ""

    if command -v whiptail &>/dev/null && { [[ -t 0 ]] || [[ -e /dev/tty ]]; }; then
        whiptail \
            --backtitle "${APP_NAME} Installer v${INSTALLER_VERSION}" \
            --title "!! ERRO !!" \
            --msgbox \
"Ocorreu um erro durante a ${_MODE:-operação}.

  Passo  : ${_CURRENT_STEP}
  Código : ${_ec}

Log completo: ${LOG}

Pode re-executar (idempotente):
  sudo bash install.sh" \
            18 64 \
            </dev/tty >/dev/tty 2>/dev/null || true
    fi

    exit "${_ec}"
}

trap 'handle_error ${LINENO}' ERR

# ─── Argumentos da CLI ────────────────────────────────────────────────────────
parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --update|-u)   _FORCE_MODE="update"  ;;
            --install|-i)  _FORCE_MODE="install" ;;
            --dir)         shift; APP_DIR="${1:-$APP_DIR}" ;;
            --port)        shift; APP_PORT="${1:-$APP_PORT}" ;;
            --help|-h)     _show_help; exit 0 ;;
            *)             _warn "Argumento desconhecido: $1" ;;
        esac
        shift
    done
}

_show_help() {
    echo ""
    printf "  ${SYM_STAMP}  ${C_BOLD}${APP_NAME} Installer v${INSTALLER_VERSION}${C_RESET}\n"
    echo ""
    echo "  Uso:"
    echo "    sudo bash install.sh [opções]"
    echo ""
    echo "  Opções:"
    echo "    --install, -i    Forçar modo instalação"
    echo "    --update, -u     Forçar modo actualização"
    echo "    --dir <path>     Directório de instalação (default: /opt/mystamps)"
    echo "    --port <port>    Porta da aplicação (default: 80)"
    echo "    --help, -h       Mostrar esta ajuda"
    echo ""
}

# ─── Detecção de Ambiente ─────────────────────────────────────────────────────

check_root() {
    if [[ $EUID -ne 0 ]]; then
        echo ""
        _fail "Execute como root ou com sudo"
        printf "  ${C_WHITE}sudo bash install.sh${C_RESET}\n"
        echo ""
        exit 1
    fi
}

detect_os() {
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        OS_ID="${ID:-unknown}"
        OS_VER="${VERSION_ID:-unknown}"
        OS_NAME="${PRETTY_NAME:-${ID}}"
    else
        OS_ID="unknown"; OS_VER="unknown"; OS_NAME="Unknown OS"
    fi
    SERVER_IP=$(hostname -I 2>/dev/null | awk '{print $1}') || SERVER_IP="127.0.0.1"
    log "SO: $OS_NAME (ID=$OS_ID VER=$OS_VER) IP=$SERVER_IP"
}

detect_lxc() {
    _IS_LXC=false
    if grep -qai "container=lxc" /proc/1/environ 2>/dev/null; then
        _IS_LXC=true; return
    fi
    if [[ -d /dev/lxc ]]; then
        _IS_LXC=true; return
    fi
    if command -v systemd-detect-virt &>/dev/null; then
        local virt
        virt=$(systemd-detect-virt 2>/dev/null || true)
        [[ "$virt" == "lxc" ]] && _IS_LXC=true
    fi
}

detect_mode() {
    if [[ -n "$_FORCE_MODE" ]]; then
        _MODE="$_FORCE_MODE"
    elif [[ -d "$APP_DIR/.git" ]] && command -v docker &>/dev/null && docker compose -f "$APP_DIR/docker-compose.yml" ps &>/dev/null 2>&1; then
        _MODE="update"
    else
        _MODE="install"
    fi
    log "Modo detectado: $_MODE (force=$_FORCE_MODE)"
}

# ─── Whiptail ─────────────────────────────────────────────────────────────────

ensure_whiptail() {
    if ! command -v whiptail &>/dev/null; then
        apt-get update -qq >> "$LOG" 2>&1 || true
        apt-get install -y -qq whiptail >> "$LOG" 2>&1 || true
    fi
}

# ─── Ecrãs Interactivos ──────────────────────────────────────────────────────

show_welcome() {
    local mode_text lxc_info env_info steps_text

    if [[ "$_MODE" == "update" ]]; then
        mode_text="MODO: ACTUALIZAÇÃO (instalação existente detectada)"
        steps_text=" [1]  Actualizar código do GitHub
 [2]  Reconstruir imagens Docker
 [3]  Reiniciar serviços
 [4]  Verificar saúde da aplicação"
    else
        mode_text="MODO: INSTALAÇÃO NOVA"
        steps_text=" [1]  Actualizar sistema operativo
 [2]  Instalar Docker CE
 [3]  Configurar Docker para o ambiente
 [4]  Descarregar ${APP_NAME} do GitHub
 [5]  Configurar variáveis de ambiente (.env)
 [6]  Compilar e iniciar todos os serviços
 [7]  Verificar saúde da aplicação"
    fi

    if [[ "$_IS_LXC" == "true" ]]; then
        lxc_info="
Ambiente: Proxmox LXC (self-healing activo)"
        env_info="
Self-healing incluído:
  - Corrige sysctl em Proxmox LXC
  - Network_mode: host em LXC
  - Fallback automático de storage driver
  - Reinício automático de contentores"
    else
        lxc_info=""
        env_info=""
    fi

    if ! command -v whiptail &>/dev/null || ! { [[ -t 0 ]] || [[ -e /dev/tty ]]; }; then
        _banner
        printf "  ${C_DIM}Sistema: ${OS_NAME}${lxc_info}${C_RESET}\n"
        printf "  ${C_DIM}Modo   : ${mode_text}${C_RESET}\n"
        echo ""
        return 0
    fi

    whiptail \
        --backtitle "${APP_NAME} Installer v${INSTALLER_VERSION}" \
        --title "${APP_NAME} — Instalador Inteligente" \
        --msgbox \
"Bem-vindo ao instalador inteligente do ${APP_NAME} v${INSTALLER_VERSION}
Colecção de Selos Filatélicos — Gerir, Catalogar, Trocar

${mode_text}

Sistema: ${OS_NAME}${lxc_info}

O instalador irá executar:
${steps_text}
${env_info}
Idempotente: pode re-executar quantas vezes quiser.

Prima OK para continuar." \
        30 68 </dev/tty >/dev/tty 2>/dev/null || true
}

confirm_proceed() {
    if ! command -v whiptail &>/dev/null || ! { [[ -t 0 ]] || [[ -e /dev/tty ]]; }; then
        return 0
    fi

    local mode_label
    if [[ "$_MODE" == "update" ]]; then
        mode_label="ACTUALIZAR"
    else
        mode_label="INSTALAR"
    fi

    whiptail \
        --backtitle "${APP_NAME} Installer v${INSTALLER_VERSION}" \
        --title "Confirmação" \
        --yesno \
"Pronto para ${mode_label} ${APP_NAME}.

  Directório : ${APP_DIR}
  Porta      : ${APP_PORT}
  Sistema    : ${OS_NAME}
  Modo       : ${_MODE^^}
  Log        : ${LOG}

Deseja continuar?" \
        16 64 </dev/tty >/dev/tty 2>/dev/null || {
        echo ""
        _warn "Operação cancelada pelo utilizador."
        exit 0
    }
}

ask_config_install() {
    if ! command -v whiptail &>/dev/null || ! { [[ -t 0 ]] || [[ -e /dev/tty ]]; }; then
        # Modo não-interactivo: gerar password automática
        DB_PASSWORD=$(openssl rand -base64 32 | tr -dc 'a-zA-Z0-9' | head -c 16)
        _info "Modo não-interactivo: password da BD gerada automaticamente."
        return 0
    fi

    APP_PORT=$(whiptail \
        --backtitle "${APP_NAME} Installer v${INSTALLER_VERSION}" \
        --title "Configuração — Porta" \
        --inputbox \
"Porta onde a aplicação ficará disponível:
  http://<IP>:<porta>

Porta (recomendado: 80):" \
        12 60 "80" 3>&1 1>&2 2>&3 </dev/tty) || exit 0

    APP_DIR=$(whiptail \
        --backtitle "${APP_NAME} Installer v${INSTALLER_VERSION}" \
        --title "Configuração — Directório" \
        --inputbox \
"Pasta onde o código será instalado:

Directório de instalação:" \
        10 60 "/opt/mystamps" 3>&1 1>&2 2>&3 </dev/tty) || exit 0

    DB_PASSWORD=$(whiptail \
        --backtitle "${APP_NAME} Installer v${INSTALLER_VERSION}" \
        --title "Configuração — Base de Dados" \
        --passwordbox \
"Password para o PostgreSQL (mínimo 8 caracteres):

Password:" \
        10 60 "" 3>&1 1>&2 2>&3 </dev/tty) || exit 0

    if [[ ${#DB_PASSWORD} -lt 8 ]]; then
        whiptail \
            --backtitle "${APP_NAME} Installer v${INSTALLER_VERSION}" \
            --title "Configuração Inválida" \
            --msgbox "Password muito curta (mínimo 8 caracteres).
Re-execute o instalador." \
            8 54 </dev/tty >/dev/tty 2>/dev/null || true
        exit 1
    fi
}

# ═══════════════════════════════════════════════════════════════════════════════
#   FUNÇÕES COMUNS (install e update)
# ═══════════════════════════════════════════════════════════════════════════════

_wait_for_docker() {
    local waited=0
    while ! docker info &>/dev/null 2>&1; do
        sleep 2; waited=$((waited + 2))
        if (( waited >= 60 )); then
            _warn "Docker não respondeu em 60s — a prosseguir"
            return 0
        fi
    done
    [[ $waited -gt 0 ]] && _info "Docker operacional após ${waited}s."
}

_heal_sysctl() {
    local current_val
    current_val=$(sysctl -n net.ipv4.ip_unprivileged_port_start 2>/dev/null || echo "?")
    if [[ "$current_val" != "0" ]]; then
        _heal "A definir net.ipv4.ip_unprivileged_port_start=0"
        sysctl -w net.ipv4.ip_unprivileged_port_start=0 >> "$LOG" 2>&1 || {
            _warn "sysctl não aceite pelo kernel — não é fatal"
        }
    fi
    echo "net.ipv4.ip_unprivileged_port_start=0" \
        > /etc/sysctl.d/99-docker-lxc.conf 2>/dev/null || true
}

_fallback_to_vfs() {
    _warn "overlay2 não funciona — a mudar para vfs..."
    systemctl stop docker docker.socket 2>/dev/null >> "$LOG" 2>&1 || true
    systemctl stop containerd 2>/dev/null >> "$LOG" 2>&1 || true
    sleep 3
    rm -rf /var/lib/docker/* /var/lib/containerd/*
    mkdir -p /etc/docker
    printf '{\n  "storage-driver": "vfs"\n}\n' > /etc/docker/daemon.json
    systemctl start containerd >> "$LOG" 2>&1 || true
    sleep 3
    systemctl start docker >> "$LOG" 2>&1 || true
    sleep 5
    _wait_for_docker
    local driver
    driver=$(docker info --format '{{.Driver}}' 2>/dev/null || echo "?")
    _heal "Storage driver alterado para: ${driver}"
}

_test_docker_quick() {
    _info "A testar se Docker consegue arrancar contentores..."

    if ! docker info &>/dev/null 2>&1; then
        systemctl start docker >> "$LOG" 2>&1 || true
        _wait_for_docker
    fi

    local test_out
    test_out=$(docker run --rm --pull=never hello-world 2>&1) || true

    if echo "$test_out" | grep -qi "Unable to find image\|No such image"; then
        _info "A descarregar imagem de teste..."
        docker pull hello-world >> "$LOG" 2>&1 || true
        test_out=$(docker run --rm hello-world 2>&1) || true
    fi

    if echo "$test_out" | grep -q "Hello from Docker"; then
        _ok "Docker funciona correctamente."
        docker rmi hello-world >> "$LOG" 2>&1 || true
        return 0
    fi

    if echo "$test_out" | grep -q "MS_PRIVATE\|remount-private"; then
        _heal "MS_PRIVATE detectado — fallback para vfs"
        _fallback_to_vfs
        test_out=$(docker run --rm hello-world 2>&1) || true
        if echo "$test_out" | grep -q "Hello from Docker"; then
            _ok "Docker OK após fallback vfs"
            docker rmi hello-world >> "$LOG" 2>&1 || true
            return 0
        fi
        _fail_nesting "$test_out"
    fi

    if echo "$test_out" | grep -q "ip_unprivileged_port_start"; then
        _warn "Erro sysctl no teste — network_mode:host irá resolver."
        docker rmi hello-world >> "$LOG" 2>&1 || true
        return 0
    fi

    if echo "$test_out" | grep -qi "failed to create shim\|runc create failed"; then
        _heal "Erro runc/shim — fallback vfs"
        _fallback_to_vfs
        test_out=$(docker run --rm hello-world 2>&1) || true
        if echo "$test_out" | grep -q "Hello from Docker"; then
            _ok "Docker OK após fallback vfs"
            docker rmi hello-world >> "$LOG" 2>&1 || true
            return 0
        fi
        if echo "$test_out" | grep -q "ip_unprivileged_port_start"; then
            _warn "Erro sysctl persistente — network_mode:host irá resolver."
            docker rmi hello-world >> "$LOG" 2>&1 || true
            return 0
        fi
        _fail_docker "$test_out"
    fi

    _warn "Resultado inesperado no teste Docker — a prosseguir."
    docker rmi hello-world >> "$LOG" 2>&1 || true
}

_fail_nesting() {
    local detail="${1:-}"
    log "ERRO nesting: ${detail}"

    echo ""
    printf "  ${C_BG_RED}${C_WHITE}${C_BOLD}  DOCKER NÃO PODE CORRER NESTE LXC  ${C_RESET}\n"
    echo ""
    _fail "O LXC não tem a opção 'nesting' activa."
    echo ""
    printf "  ${C_YELLOW}SOLUÇÃO — executar NO HOST PROXMOX:${C_RESET}\n"
    echo ""
    printf "    ${C_WHITE}1.${C_RESET} pct list\n"
    printf "    ${C_WHITE}2.${C_RESET} pct set XXX --features nesting=1,keyctl=1\n"
    printf "    ${C_WHITE}3.${C_RESET} pct stop XXX && pct start XXX\n"
    printf "    ${C_WHITE}4.${C_RESET} Re-executar: bash install.sh\n"
    echo ""

    if command -v whiptail &>/dev/null; then
        whiptail \
            --backtitle "${APP_NAME} Installer v${INSTALLER_VERSION}" \
            --title "Configuração Proxmox Necessária" \
            --msgbox \
"Docker não consegue correr contentores.

SOLUÇÃO — no HOST Proxmox:

  1. pct list
  2. pct set XXX --features nesting=1,keyctl=1
  3. pct stop XXX && pct start XXX
  4. Re-executar: bash install.sh" \
            16 60 \
            </dev/tty >/dev/tty 2>/dev/null || true
    fi
    exit 1
}

_fail_docker() {
    local detail="${1:-}"
    log "ERRO Docker fatal: ${detail}"
    _fail "Docker não funciona. Detalhe: ${detail}"
    printf "  ${C_DIM}Log: ${LOG}${C_RESET}\n"
    exit 1
}

# ═══════════════════════════════════════════════════════════════════════════════
#   PASSOS DE INSTALAÇÃO NOVA
# ═══════════════════════════════════════════════════════════════════════════════

install_step_system() {
    _step_header "Actualizar sistema operativo" "${SYM_GEAR}"
    export DEBIAN_FRONTEND=noninteractive

    _spin "A executar apt-get update..." \
        apt-get update -qq

    _spin "A actualizar pacotes instalados..." \
        apt-get upgrade -y -qq

    _spin "A instalar dependências básicas..." \
        apt-get install -y -qq \
            curl wget git ca-certificates gnupg \
            lsb-release apt-transport-https \
            software-properties-common \
            openssl python3

    _ok "Sistema actualizado."
}

install_step_docker() {
    _step_header "Instalar Docker CE" "${SYM_DOCKER}"

    if command -v docker &>/dev/null; then
        _ok "Docker já instalado: $(docker --version 2>/dev/null | head -1)"
        if docker compose version &>/dev/null; then
            _ok "Docker Compose: $(docker compose version 2>/dev/null | head -1)"
        else
            _heal "Docker Compose plugin em falta"
            _spin "A instalar docker-compose-plugin..." \
                apt-get install -y -qq docker-compose-plugin
        fi
        systemctl start docker >> "$LOG" 2>&1 || true
        _wait_for_docker
        return 0
    fi

    _info "A remover versões antigas do Docker..."
    apt-get remove -y -qq \
        docker docker-engine docker.io containerd runc \
        2>/dev/null >> "$LOG" 2>&1 || true

    _spin "A configurar repositório oficial Docker..." \
        bash -c '
            install -m 0755 -d /etc/apt/keyrings
            if [[ "'"$OS_ID"'" == "ubuntu" ]]; then
                curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
                    | gpg --dearmor --yes -o /etc/apt/keyrings/docker.gpg
                chmod a+r /etc/apt/keyrings/docker.gpg
                echo \
                  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
                   https://download.docker.com/linux/ubuntu \
                   $(lsb_release -cs) stable" \
                  > /etc/apt/sources.list.d/docker.list
            else
                curl -fsSL https://download.docker.com/linux/debian/gpg \
                    | gpg --dearmor --yes -o /etc/apt/keyrings/docker.gpg
                chmod a+r /etc/apt/keyrings/docker.gpg
                echo \
                  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
                   https://download.docker.com/linux/debian \
                   $(lsb_release -cs) stable" \
                  > /etc/apt/sources.list.d/docker.list
            fi
        '

    _spin "A instalar Docker CE e Compose..." \
        bash -c 'apt-get update -qq && apt-get install -y -qq \
            docker-ce docker-ce-cli containerd.io \
            docker-buildx-plugin docker-compose-plugin'

    systemctl enable docker >> "$LOG" 2>&1
    systemctl start docker  >> "$LOG" 2>&1 || true

    _wait_for_docker

    _ok "Docker: $(docker --version 2>/dev/null | head -1)"
    _ok "Compose: $(docker compose version 2>/dev/null | head -1)"
}

install_step_configure_lxc() {
    _step_header "Configurar Docker para o ambiente" "${SYM_GEAR}"

    if [[ "$_IS_LXC" == "true" ]]; then
        _info "Ambiente: Proxmox LXC detectado"
        _heal_sysctl
    else
        _info "Ambiente: VM ou bare-metal (config LXC não necessária)"
    fi

    _test_docker_quick
}

install_step_clone() {
    _step_header "Descarregar ${APP_NAME} do GitHub" "📥"

    mkdir -p "$APP_DIR"

    if [[ -d "$APP_DIR/.git" ]]; then
        _info "Repositório já existe — a actualizar..."
        _spin "A fazer git pull..." \
            git -C "$APP_DIR" pull
    else
        _spin "A clonar repositório..." \
            git clone "$REPO_URL" "$APP_DIR"
    fi

    _ok "Código em: ${APP_DIR}"
}

install_step_env() {
    _step_header "Configurar ambiente (.env)" "${SYM_KEY}"

    if [[ -f "$APP_DIR/.env" ]]; then
        _ok "Ficheiro .env já existe — preservado."
    else
        SECRET_KEY=$(openssl rand -base64 64 | tr -dc 'a-zA-Z0-9!@#%^&*(-_=+)' | head -c 50)
        local allowed_hosts="localhost,127.0.0.1,${SERVER_IP}"

        cat > "$APP_DIR/.env" << ENV_CONTENT
# =============================================================================
# ${APP_NAME} — Configuração de Produção
# Gerado pelo instalador v${INSTALLER_VERSION} em $(date)
# NÃO partilhe este ficheiro — contém credenciais
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
        _ok ".env criado (ALLOWED_HOSTS: ${allowed_hosts})"
    fi

    # docker-compose adaptado para LXC
    if [[ "$_IS_LXC" == "true" ]]; then
        _info "Proxmox LXC: a gerar docker-compose.yml com network_mode: host"
        _generate_compose_host
    else
        _info "A usar docker-compose.yml original (bridge networking)"
    fi

    _configure_port
    _ok "Ambiente configurado."
}

_generate_compose_host() {
    local compose_file="$APP_DIR/docker-compose.yml"

    if [[ -f "$compose_file" ]]; then
        cp "$compose_file" "${compose_file}.original"
    fi

    cat > "$compose_file" << 'COMPOSE_CONTENT'
# =============================================================================
# myStampsCollection — docker-compose.yml (Proxmox LXC)
# network_mode: host — evita erros de sysctl/namespace em LXC
# Gerado automaticamente pelo instalador
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

    if [[ -f "$APP_DIR/.env" ]]; then
        sed -i 's/^DB_HOST=.*/DB_HOST=127.0.0.1/' "$APP_DIR/.env"
    fi

    local nginx_conf="$APP_DIR/docker/nginx/default.conf"
    if [[ -f "$nginx_conf" ]]; then
        sed -i 's/server web:8000;/server 127.0.0.1:8000;/' "$nginx_conf"
    fi
}

_configure_port() {
    if [[ "$APP_PORT" == "80" ]]; then return 0; fi

    _info "A ajustar porta para ${APP_PORT}..."

    local nginx_conf="$APP_DIR/docker/nginx/default.conf"
    if [[ -f "$nginx_conf" ]]; then
        sed -i "s/listen 80;/listen ${APP_PORT};/" "$nginx_conf"
    fi

    local compose_file="$APP_DIR/docker-compose.yml"
    if [[ -f "$compose_file" ]] && grep -q '"80:80"' "$compose_file"; then
        sed -i "s/\"80:80\"/\"${APP_PORT}:${APP_PORT}\"/" "$compose_file"
    fi
}

install_step_build() {
    _step_header "Compilar e iniciar serviços" "${SYM_ROCKET}"

    _info "A compilação pode demorar vários minutos..."
    echo ""

    cd "$APP_DIR"

    local build_ok=false
    for attempt in 1 2 3; do
        _info "Build Docker: tentativa ${attempt}/3..."
        if docker compose -f docker-compose.yml build 2>&1 | tee -a "$LOG"; then
            build_ok=true
            break
        fi
        _warn "Build falhou na tentativa ${attempt}/3"
        if (( attempt < 3 )); then
            _heal "A limpar cache Docker e a re-tentar..."
            docker builder prune -f >> "$LOG" 2>&1 || true
            sleep 5
        fi
    done

    if [[ "$build_ok" != "true" ]]; then
        _fail "Build falhou após 3 tentativas."
        printf "  ${C_DIM}Verifique a ligação à Internet e espaço em disco.${C_RESET}\n"
        exit 1
    fi

    _ok "Build concluído."
    echo ""

    _start_services
}

_start_services() {
    cd "$APP_DIR"
    _info "A iniciar serviços..."

    docker compose -f docker-compose.yml down 2>/dev/null >> "$LOG" 2>&1 || true

    local start_out
    start_out=$(docker compose -f docker-compose.yml up -d 2>&1) || true
    echo "$start_out" >> "$LOG"

    if echo "$start_out" | grep -q "ip_unprivileged_port_start"; then
        _heal "Erro sysctl no arranque — a re-aplicar e re-tentar"
        _heal_sysctl
        docker compose -f docker-compose.yml down 2>/dev/null >> "$LOG" 2>&1 || true
        start_out=$(docker compose -f docker-compose.yml up -d 2>&1) || true
        echo "$start_out" >> "$LOG"
    fi

    if echo "$start_out" | grep -qi "failed to create shim\|runc create failed"; then
        _heal "Erro runc no arranque — fallback vfs"
        _fallback_to_vfs
        docker compose -f docker-compose.yml down 2>/dev/null >> "$LOG" 2>&1 || true
        start_out=$(docker compose -f docker-compose.yml up -d 2>&1) || true
        echo "$start_out" >> "$LOG"
    fi

    sleep 5

    for svc in db web nginx; do
        local cstatus
        cstatus=$(docker inspect --format='{{.State.Status}}' "stamps_${svc}" 2>/dev/null || echo "missing")
        if [[ "$cstatus" != "running" ]]; then
            _heal "A reiniciar stamps_${svc} (estado: ${cstatus})"
            docker start "stamps_${svc}" >> "$LOG" 2>&1 || true
            sleep 3
        fi
    done

    _ok "Serviços iniciados."
}

# ═══════════════════════════════════════════════════════════════════════════════
#   PASSOS DE ACTUALIZAÇÃO
# ═══════════════════════════════════════════════════════════════════════════════

update_step_pull() {
    _step_header "Actualizar código do GitHub" "📥"

    if [[ ! -d "$APP_DIR/.git" ]]; then
        _fail "Directório ${APP_DIR} não é um repositório git."
        _info "Execute sem --update para uma instalação nova."
        exit 1
    fi

    # Guardar versão anterior
    local prev_hash
    prev_hash=$(git -C "$APP_DIR" rev-parse --short HEAD 2>/dev/null || echo "?")

    _spin "A fazer git pull..." \
        git -C "$APP_DIR" pull

    local new_hash
    new_hash=$(git -C "$APP_DIR" rev-parse --short HEAD 2>/dev/null || echo "?")

    if [[ "$prev_hash" == "$new_hash" ]]; then
        _ok "Código já actualizado (${new_hash}) — sem alterações."
    else
        _ok "Actualizado: ${prev_hash} → ${new_hash}"
    fi
}

update_step_build() {
    _step_header "Reconstruir imagens Docker" "${SYM_DOCKER}"

    cd "$APP_DIR"

    _info "A reconstruir (pode demorar)..."
    if docker compose -f docker-compose.yml build --pull=never 2>&1 | tee -a "$LOG"; then
        _ok "Build concluído."
    else
        _warn "Build com cache falhou — a tentar build completo..."
        _heal "Retry de build sem cache"
        docker builder prune -f >> "$LOG" 2>&1 || true
        docker compose -f docker-compose.yml build 2>&1 | tee -a "$LOG"
        _ok "Build concluído (sem cache)."
    fi
}

update_step_restart() {
    _step_header "Reiniciar serviços" "${SYM_ROCKET}"

    cd "$APP_DIR"

    _info "A reiniciar contentores..."
    docker compose -f docker-compose.yml down >> "$LOG" 2>&1 || true
    docker compose -f docker-compose.yml up -d 2>&1 | tee -a "$LOG"

    sleep 5

    for svc in db web nginx; do
        local cstatus
        cstatus=$(docker inspect --format='{{.State.Status}}' "stamps_${svc}" 2>/dev/null || echo "missing")
        if [[ "$cstatus" == "running" ]]; then
            _ok "stamps_${svc}: running"
        else
            _heal "A reiniciar stamps_${svc} (${cstatus})"
            docker start "stamps_${svc}" >> "$LOG" 2>&1 || true
            sleep 3
        fi
    done

    _ok "Serviços reiniciados."
}

# ═══════════════════════════════════════════════════════════════════════════════
#   VERIFICAÇÃO DE SAÚDE (comum a install e update)
# ═══════════════════════════════════════════════════════════════════════════════

step_health_check() {
    local step_icon="🏥"
    _step_header "Verificação de saúde" "$step_icon"

    local all_ok=true

    # ── Contentores ───────────────────────────────────────────────────────────
    printf "\n  ${C_BOLD}Estado dos contentores:${C_RESET}\n\n"

    for svc in db web nginx; do
        local cname="stamps_${svc}"
        local cstatus health_str icon

        cstatus=$(docker inspect --format='{{.State.Status}}' "$cname" 2>/dev/null || echo "not-found")
        health_str=$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}n/a{{end}}' "$cname" 2>/dev/null || echo "n/a")

        if [[ "$cstatus" == "running" ]]; then
            icon="${C_GREEN}${SYM_DOT}${C_RESET}"
        else
            icon="${C_RED}${SYM_DOT}${C_RESET}"
            all_ok=false
        fi

        local label_padded
        label_padded=$(printf "%-14s" "$cname")
        printf "    ${icon}  ${C_WHITE}${label_padded}${C_RESET}"
        printf "  estado: ${C_BOLD}%-10s${C_RESET}" "$cstatus"
        if [[ "$health_str" != "n/a" ]]; then
            printf "  health: ${C_BOLD}%s${C_RESET}" "$health_str"
        fi
        echo ""
    done

    echo ""

    # ── HTTP ──────────────────────────────────────────────────────────────────
    _info "A aguardar resposta HTTP..."
    local waited=0 http_ok=false http_code="000"

    while true; do
        http_code=$(curl -sf -o /dev/null -w "%{http_code}" "http://localhost:${APP_PORT}" 2>/dev/null || echo "000")

        if [[ "$http_code" =~ ^(200|301|302)$ ]]; then
            http_ok=true
            break
        fi

        local web_status
        web_status=$(docker inspect --format='{{.State.Status}}' stamps_web 2>/dev/null || echo "unknown")
        if [[ "$web_status" == "exited" || "$web_status" == "dead" ]]; then
            _heal "stamps_web parou — a reiniciar"
            docker start stamps_web >> "$LOG" 2>&1 || true
        fi

        sleep 5; waited=$((waited + 5))
        printf "\r  ${C_DIM}  A aguardar... %ds (HTTP %s)${C_RESET}" "$waited" "$http_code"

        if (( waited >= 180 )); then
            echo ""
            _warn "Timeout (180s) — migrações/fixtures podem estar em curso."
            _info "Verifique: docker logs stamps_web -f"
            break
        fi
    done

    if [[ $waited -gt 0 ]]; then echo ""; fi

    if [[ "$http_ok" == "true" ]]; then
        _ok "Aplicação a responder (HTTP ${http_code})"
    else
        all_ok=false
    fi

    # ── Disco ─────────────────────────────────────────────────────────────────
    local disk_usage
    disk_usage=$(df -h / 2>/dev/null | awk 'NR==2{print $5}' | tr -d '%')
    if [[ -n "$disk_usage" ]]; then
        if (( disk_usage > 90 )); then
            _warn "Disco quase cheio: ${disk_usage}% usado"
        else
            _ok "Disco: ${disk_usage}% usado"
        fi
    fi

    # ── Resumo ────────────────────────────────────────────────────────────────
    echo ""
    if [[ "$all_ok" == "true" ]]; then
        printf "  ${C_BG_GREEN}${C_WHITE}${C_BOLD}  ${SYM_OK}  TUDO OK — Aplicação saudável!  ${C_RESET}\n"
    else
        printf "  ${C_YELLOW}${C_BOLD}  ${SYM_WARN}Alguns problemas detectados — verificar logs  ${C_RESET}\n"
    fi
}

# ═══════════════════════════════════════════════════════════════════════════════
#   SCRIPT DE ACTUALIZAÇÃO + RESUMO FINAL
# ═══════════════════════════════════════════════════════════════════════════════

_install_update_script() {
    local src="$APP_DIR/setup/update.sh"
    local dest="/usr/local/bin/mystamps-update"

    if [[ -f "$src" ]]; then
        cp "$src" "$dest"
        chmod +x "$dest"
        sed -i "s|APP_DIR=\"/opt/mystamps\"|APP_DIR=\"${APP_DIR}\"|" "$dest"
        _ok "Comando de actualização: mystamps-update"
    fi

    # Também instalar atalho para re-executar o instalador
    local installer_link="/usr/local/bin/mystamps-setup"
    cat > "$installer_link" << SETUP_SCRIPT
#!/bin/bash
# Atalho para o instalador inteligente do ${APP_NAME}
exec bash "${APP_DIR}/setup/install.sh" "\$@"
SETUP_SCRIPT
    chmod +x "$installer_link"
    _ok "Comando de setup: mystamps-setup"
}

_show_final_summary() {
    local elapsed=$(( $(date +%s) - _START_TIME ))
    local mins=$(( elapsed / 60 ))
    local secs=$(( elapsed % 60 ))

    local mode_label mode_color
    if [[ "$_MODE" == "update" ]]; then
        mode_label="ACTUALIZADA"
        mode_color="${C_CYAN}"
    else
        mode_label="INSTALADA"
        mode_color="${C_GREEN}"
    fi

    # Guardar resumo em ficheiro
    local summary_file="/root/mystamps-access.txt"
    cat > "$summary_file" << SUMMARY_EOF
======================================================================
  ${APP_NAME} — RESUMO DE ACESSO
  ${_MODE^} em: $(date)
  Versão instalador: ${INSTALLER_VERSION}
======================================================================

  Aplicação  -->  http://${SERVER_IP}:${APP_PORT}
  Admin      -->  http://${SERVER_IP}:${APP_PORT}/admin/

  Primeiro acesso:
    1. Aceder a http://${SERVER_IP}:${APP_PORT}
    2. Registar uma conta em "Registar"
    3. Criar superutilizador:
       docker exec -it stamps_web python manage.py createsuperuser

  COMANDOS ÚTEIS:
    Actualizar:     mystamps-update
    Re-setup:       mystamps-setup
    Ver logs web:   docker logs stamps_web -f
    Ver logs db:    docker logs stamps_db -f
    Ver logs nginx: docker logs stamps_nginx -f
    Parar:          docker compose -f ${APP_DIR}/docker-compose.yml down
    Reiniciar:      docker compose -f ${APP_DIR}/docker-compose.yml restart
    Log instalação: ${LOG}

  Self-heal: ${_HEAL_ACTIONS} acções de auto-reparação
======================================================================
SUMMARY_EOF

    # Terminal
    echo ""
    echo ""
    printf "${C_BOLD}${C_BLUE}"
    echo "  ╔════════════════════════════════════════════════════════════════╗"
    echo "  ║                                                              ║"
    printf "  ║  ${SYM_STAMP}  ${C_WHITE}${APP_NAME}${C_BLUE}  —  ${mode_color}${mode_label}!${C_BLUE}                  ║\n"
    echo "  ║                                                              ║"
    echo "  ╠════════════════════════════════════════════════════════════════╣"
    echo "  ║                                                              ║"
    printf "  ║  ${C_WHITE}${SYM_LINK} ACESSOS:${C_BLUE}                                                ║\n"
    echo "  ║                                                              ║"
    printf "  ║   ${C_GREEN}Aplicação${C_RESET}${C_BLUE}  ${SYM_ARROW}  ${C_WHITE}http://${SERVER_IP}:${APP_PORT}${C_BLUE}            ║\n"
    printf "  ║   ${C_CYAN}Admin${C_RESET}${C_BLUE}      ${SYM_ARROW}  ${C_WHITE}http://${SERVER_IP}:${APP_PORT}/admin/${C_BLUE}     ║\n"
    echo "  ║                                                              ║"
    echo "  ╠════════════════════════════════════════════════════════════════╣"
    echo "  ║                                                              ║"
    printf "  ║  ${C_WHITE}${SYM_STAR} PRIMEIRO ACESSO:${C_BLUE}                                        ║\n"
    echo "  ║                                                              ║"
    printf "  ║   ${C_DIM}1. Abrir a aplicação no browser${C_BLUE}                         ║\n"
    printf "  ║   ${C_DIM}2. Registar uma conta${C_BLUE}                                   ║\n"
    printf "  ║   ${C_DIM}3. Criar superutilizador:${C_BLUE}                               ║\n"
    printf "  ║      ${C_WHITE}docker exec -it stamps_web \\\\${C_BLUE}                      ║\n"
    printf "  ║        ${C_WHITE}python manage.py createsuperuser${C_BLUE}                  ║\n"
    echo "  ║                                                              ║"
    echo "  ╠════════════════════════════════════════════════════════════════╣"
    echo "  ║                                                              ║"
    printf "  ║  ${C_WHITE}${SYM_GEAR}COMANDOS ÚTEIS:${C_BLUE}                                          ║\n"
    echo "  ║                                                              ║"
    printf "  ║   ${C_WHITE}mystamps-update${C_BLUE}            Actualizar                  ║\n"
    printf "  ║   ${C_WHITE}mystamps-setup${C_BLUE}             Re-executar setup            ║\n"
    printf "  ║   ${C_WHITE}docker logs stamps_web -f${C_BLUE}  Ver logs                    ║\n"
    echo "  ║                                                              ║"

    if (( _HEAL_ACTIONS > 0 )); then
        echo "  ╠════════════════════════════════════════════════════════════════╣"
        echo "  ║                                                              ║"
        printf "  ║  ${C_MAGENTA}${SYM_HEAL} Self-healing: %d acções aplicadas${C_BLUE}                      ║\n" "$_HEAL_ACTIONS"
        echo "  ║                                                              ║"
    fi

    echo "  ╠════════════════════════════════════════════════════════════════╣"
    echo "  ║                                                              ║"
    printf "  ║  ${C_DIM}${SYM_CLOCK}Tempo total: %02d:%02d${C_BLUE}                                     ║\n" "$mins" "$secs"
    printf "  ║  ${C_DIM}📋 Resumo: ${summary_file}${C_BLUE}       ║\n"
    printf "  ║  ${C_DIM}📝 Log   : ${LOG}${C_BLUE}  ║\n"
    echo "  ║                                                              ║"
    echo "  ╚════════════════════════════════════════════════════════════════╝"
    printf "${C_RESET}\n"

    log "=== ${_MODE^} concluída (tempo: ${mins}m${secs}s, self-heal: ${_HEAL_ACTIONS}) ==="
}

# ═══════════════════════════════════════════════════════════════════════════════
#   PROGRAMA PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════════

main() {
    : > "$LOG"
    log "${APP_NAME} Installer v${INSTALLER_VERSION} — $(date)"

    parse_args "$@"
    check_root
    ensure_whiptail
    detect_os
    detect_lxc
    detect_mode

    log "Modo: ${_MODE}  LXC: ${_IS_LXC}  OS: ${OS_NAME}  IP: ${SERVER_IP}"

    if [[ "$_MODE" == "update" ]]; then
        _TOTAL_STEPS=4
    else
        _TOTAL_STEPS=7
    fi

    show_welcome

    if [[ "$_MODE" == "install" ]]; then
        ask_config_install
        # Re-detect mode pois APP_DIR pode ter mudado
        detect_mode
    else
        # Em update, ler APP_DIR do script existente
        if [[ -f "/usr/local/bin/mystamps-update" ]]; then
            local detected_dir
            detected_dir=$(grep '^APP_DIR=' /usr/local/bin/mystamps-update 2>/dev/null | head -1 | cut -d'"' -f2)
            if [[ -n "$detected_dir" && -d "$detected_dir" ]]; then
                APP_DIR="$detected_dir"
            fi
        fi
        # Ler porta do nginx config existente
        local nginx_conf="$APP_DIR/docker/nginx/default.conf"
        if [[ -f "$nginx_conf" ]]; then
            local detected_port
            detected_port=$(grep 'listen ' "$nginx_conf" 2>/dev/null | head -1 | awk '{print $2}' | tr -d ';')
            if [[ -n "$detected_port" && "$detected_port" =~ ^[0-9]+$ ]]; then
                APP_PORT="$detected_port"
            fi
        fi
    fi

    confirm_proceed

    _banner

    printf "  ${C_DIM}Sistema : ${OS_NAME}${C_RESET}\n"
    printf "  ${C_DIM}IP      : ${SERVER_IP}${C_RESET}\n"
    printf "  ${C_DIM}Modo    : ${_MODE^^}${C_RESET}\n"
    if [[ "$_IS_LXC" == "true" ]]; then
        printf "  ${C_DIM}Ambiente: Proxmox LXC (self-healing activo)${C_RESET}\n"
    fi
    printf "  ${C_DIM}Log     : ${LOG}${C_RESET}\n"

    # ══════════════════════════════════════════════════════════════════════════
    #  EXECUTAR PASSOS
    # ══════════════════════════════════════════════════════════════════════════

    if [[ "$_MODE" == "install" ]]; then
        _progress_bar 5 "Iniciar instalação..."

        install_step_system
        _progress_bar 15 "Sistema actualizado"

        install_step_docker
        _progress_bar 30 "Docker instalado"

        install_step_configure_lxc
        _progress_bar 40 "Docker configurado"

        install_step_clone
        _progress_bar 50 "Código descarregado"

        install_step_env
        _progress_bar 55 "Ambiente configurado"

        install_step_build
        _progress_bar 80 "Serviços compilados e iniciados"

        step_health_check
        _progress_bar 95 "Saúde verificada"

        _install_update_script
        _progress_bar 100 "Instalação completa!"

    else
        _progress_bar 5 "Iniciar actualização..."

        update_step_pull
        _progress_bar 30 "Código actualizado"

        update_step_build
        _progress_bar 60 "Imagens reconstruídas"

        update_step_restart
        _progress_bar 80 "Serviços reiniciados"

        step_health_check
        _progress_bar 95 "Saúde verificada"

        _install_update_script
        _progress_bar 100 "Actualização completa!"
    fi

    trap '' ERR
    _show_final_summary
}

main "$@"
exit 0
