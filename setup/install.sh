#!/usr/bin/env bash
# ===============================================================================
#
#   myStampsCollection  --  Instalador Automático  v1.0
#
#   Plataforma web de gestão de coleções de selos filatélicos
#   Django + PostgreSQL + Gunicorn + Nginx + Docker
#
#   Suporta: Debian 11/12 · Ubuntu 22.04/24.04
#   Destino:  LXC em Proxmox (acabado de criar, sem Docker)
#
#   Uso:
#       bash install.sh            (como root ou com sudo)
#       sudo bash install.sh
#
# ===============================================================================

set -euo pipefail

# -- Constantes -----------------------------------------------------------------
readonly REPO_URL="https://github.com/mbangas/myStampsCollection.git"
readonly LOG="/tmp/mystamps_install_$(date +%Y%m%d_%H%M%S).log"

APP_DIR="/opt/mystamps"
APP_PORT="80"
PORTAINER_PORT="9000"
DB_PASSWORD=""
SECRET_KEY=""

OS_ID=""
OS_VER=""
OS_NAME=""
SERVER_IP=""

_CURRENT_STEP="(inicializacao)"

# -- Utilitários de log ---------------------------------------------------------
log()  { echo "[$(date '+%H:%M:%S')] $*" >> "$LOG"; }
info() { echo "  --> $*"; log "$*"; }
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
    # Desactivar o trap imediatamente para evitar recursao
    trap '' ERR

    # Guardar o codigo de saida ANTES de qualquer outro comando
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

    if command -v whiptail &>/dev/null && [[ -t 0 ]] || [[ -e /dev/tty ]]; then
        whiptail \
            --backtitle "myStampsCollection Installer  v1.0" \
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

Pode re-executar:
  sudo bash install.sh" \
            28 68 \
            </dev/tty >/dev/tty 2>/dev/null || true
    fi

    exit "${_ec}"
}

trap 'handle_error ${LINENO}' ERR

# -- Progresso no CLI -----------------------------------------------------------
progress() {   # progress <pct> <mensagem>
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
        apt-get update -qq && apt-get install -y -qq whiptail
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

# -- Ecra de boas-vindas --------------------------------------------------------
show_welcome() {
    whiptail \
        --backtitle "myStampsCollection Installer  v1.0" \
        --title "myStampsCollection -- Instalador" \
        --msgbox \
"Bem-vindo ao instalador do myStampsCollection v1.0
Colecao de Selos Filatelicos -- Gerir, Catalogar, Trocar

Sistema detectado: ${OS_NAME}

O instalador ira executar automaticamente:

 [1]  Actualizar o sistema operativo
 [2]  Instalar Docker CE
 [3]  Descarregar myStampsCollection do GitHub
 [4]  Configurar variaveis de ambiente (.env)
 [5]  Compilar as imagens Docker e iniciar servicos

ATENCAO: Este processo pode demorar varios minutos
(5 a 20 min dependendo da ligacao a Internet e
dos recursos do servidor). Por favor aguarde.

Prima OK para continuar." \
        26 64
}

# -- Confirmacao ----------------------------------------------------------------
confirm_install() {
    whiptail \
        --backtitle "myStampsCollection Installer  v1.0" \
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
    # Porta da aplicacao
    APP_PORT=$(whiptail \
        --backtitle "myStampsCollection Installer  v1.0" \
        --title "Configuracao -- Porta da Aplicacao" \
        --inputbox \
"Porta onde o myStampsCollection ficara disponivel.

Depois da instalacao, a aplicacao estara
acessivel em:
  http://<IP-do-servidor>:<porta>

Porta (recomendado: 80):" \
        14 60 "80" 3>&1 1>&2 2>&3) || exit 0

    # Directorio de instalacao
    APP_DIR=$(whiptail \
        --backtitle "myStampsCollection Installer  v1.0" \
        --title "Configuracao -- Directorio de Instalacao" \
        --inputbox \
"Pasta onde o codigo da aplicacao sera instalado.
(Git clone do repositorio)

Directorio de instalacao:" \
        10 60 "/opt/mystamps" 3>&1 1>&2 2>&3) || exit 0

    # Password da base de dados
    DB_PASSWORD=$(whiptail \
        --backtitle "myStampsCollection Installer  v1.0" \
        --title "Configuracao -- Base de Dados PostgreSQL" \
        --passwordbox \
"Password para a base de dados PostgreSQL.

Use uma password segura (minimo 8 caracteres).
Esta password e guardada no ficheiro .env.

Password da base de dados:" \
        13 60 "" 3>&1 1>&2 2>&3) || exit 0

    # Validar password
    if [[ ${#DB_PASSWORD} -lt 8 ]]; then
        whiptail \
            --backtitle "myStampsCollection Installer  v1.0" \
            --title "Configuracao Invalida" \
            --msgbox "A password deve ter pelo menos 8 caracteres.

Por favor reinicie o instalador e use
uma password mais longa." \
            10 54
        exit 1
    fi
}

# -- PASSO 1: Actualizar sistema ------------------------------------------------
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

# -- PASSO 2: Instalar Docker CE ------------------------------------------------
step_install_docker() {
    step "PASSO 2/5: Instalar Docker CE"

    if command -v docker &>/dev/null; then
        info "Docker ja esta instalado: $(docker --version)"
        # Garantir que o plugin compose tambem esta presente
        if docker compose version &>/dev/null; then
            info "Docker Compose ja disponivel: $(docker compose version)"
            return 0
        fi
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
        # Debian
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

    info "A iniciar servico Docker..."
    systemctl enable docker                                 >> "$LOG" 2>&1
    systemctl start docker                                  >> "$LOG" 2>&1

    info "Docker instalado: $(docker --version)"
    info "Docker Compose instalado: $(docker compose version)"
}

# -- Configurar storage driver do Docker para Proxmox LXC ---------------------
# Limpa o estado anterior e reinicia o Docker de raiz.
# Se overlay2 funcionar (LXC com nesting=1) usa overlay2.
# Se falhar com MS_PRIVATE (sem nesting), faz fallback automatico para vfs.
step_fix_lxc_overlay() {
    info "A configurar storage driver para Proxmox LXC..."

    # Parar Docker e limpar estado de tentativas anteriores
    systemctl stop docker docker.socket 2>/dev/null            >> "$LOG" 2>&1 || true
    systemctl stop containerd                                  >> "$LOG" 2>&1 || true
    sleep 3
    info "A limpar dados anteriores do Docker..."
    rm -rf /var/lib/docker/* /var/lib/containerd/*
    log "Dados anteriores removidos"

    # Remover daemon.json de tentativas anteriores para deixar Docker
    # usar overlay2 por omissao (funciona em LXC com nesting=1)
    rm -f /etc/docker/daemon.json
    log "daemon.json removido -- Docker vai usar driver por omissao (overlay2)"

    # Iniciar Docker
    info "A iniciar Docker..."
    systemctl start containerd                                 >> "$LOG" 2>&1
    sleep 3
    systemctl start docker                                     >> "$LOG" 2>&1
    sleep 5

    local active_driver
    active_driver=$(docker info --format '{{.Driver}}' 2>/dev/null || echo "?")
    info "Storage driver activo: ${active_driver}"
    log "Storage driver inicial: ${active_driver}"

    # Permitir que processos sem root abram portas baixas (<=80) dentro dos
    # contentores -- necessario em Proxmox LXC onde o runc nao tem permissao
    # para escrever este sysctl no namespace de rede do contentor.
    info "A configurar net.ipv4.ip_unprivileged_port_start (Proxmox LXC)..."
    sysctl -w net.ipv4.ip_unprivileged_port_start=0             >> "$LOG" 2>&1 || true
    echo "net.ipv4.ip_unprivileged_port_start=0" \
        > /etc/sysctl.d/99-docker-lxc.conf
    log "net.ipv4.ip_unprivileged_port_start=0 definido e persistido."
}

# -- Mostrar erro de nesting Proxmox e parar -----------------------------------
_fail_nesting() {
    local detail="${1:-}"
    log "ERRO nesting: ${detail}"

    echo "" >&2
    echo "======================================================================" >&2
    echo "  ERRO: Docker nao pode arrancar contentores neste LXC"                >&2
    echo "======================================================================" >&2
    echo "" >&2
    echo "  Causa: o LXC Proxmox nao tem a opcao 'nesting' activa."             >&2
    echo "  Sem ela, o Docker nao consegue correr NENHUM contentor."            >&2
    echo "" >&2
    echo "  SOLUCAO -- executar NO HOST PROXMOX:"                               >&2
    echo "" >&2
    echo "    1. Ver o ID deste LXC:"                                            >&2
    echo "         pct list"                                                      >&2
    echo "" >&2
    echo "    2. Activar nesting (substituir XXX pelo ID do LXC):"              >&2
    echo "         pct set XXX --features nesting=1,keyctl=1"                    >&2
    echo "" >&2
    echo "    3. Reiniciar o LXC:"                                               >&2
    echo "         pct stop XXX && pct start XXX"                                >&2
    echo "" >&2
    echo "    4. Voltar a executar o instalador dentro do LXC:"                 >&2
    echo "         bash install.sh"                                               >&2
    echo "" >&2
    echo "  Alternativa (interface Proxmox):"                                    >&2
    echo "    Container > Options > Features > Nesting (activar checkmark)"      >&2
    echo "" >&2

    whiptail \
        --backtitle "myStampsCollection Installer  v1.0" \
        --title "Configuracao Proxmox Necessaria" \
        --msgbox \
"O Docker nao consegue correr contentores.

A opcao 'nesting' nao esta activa neste LXC.

SOLUCAO -- no HOST Proxmox:

  1. Ver o ID deste LXC:
       pct list

  2. Activar nesting (mudar XXX pelo ID):
       pct set XXX --features nesting=1,keyctl=1

  3. Reiniciar o LXC:
       pct stop XXX && pct start XXX

  4. Re-executar o instalador:
       bash install.sh

Alternativa (interface Proxmox):
  Container > Options > Features
  -> activar 'Nesting'" \
        26 64 \
        </dev/tty >/dev/tty 2>/dev/null || true

    exit 1
}

# -- Verificar que o Docker consegue arrancar contentores ----------------------
# Testa com --pull=never (sem rede) para detectar MS_PRIVATE (falta de nesting).
# Se MS_PRIVATE detectado: fallback automatico para vfs e re-teste.
# So pede intervencao manual se ainda falhar apos fallback.
check_docker_works() {
    info "A verificar compatibilidade Docker/LXC..."

    local cur_driver
    cur_driver=$(docker info --format '{{.Driver}}' 2>/dev/null || echo "?")
    info "Storage driver: ${cur_driver}"
    log "Storage driver em uso: ${cur_driver}"

    # Testar nesting: usar imagem hello-world se ja estiver em cache
    info "A verificar permissoes do LXC (nesting)..."
    local nest_err
    nest_err=$(docker run --rm --pull=never hello-world 2>&1) || true

    if echo "$nest_err" | grep -qi "Unable to find image\|No such image"; then
        # Imagem nao em cache -- nao e erro de nesting, pode prosseguir
        log "check_docker_works: imagem local ausente -- verificacao de nesting ignorada"
        info "Verificacao de nesting ignorada (imagem local ausente)."
        return 0
    fi

    if echo "$nest_err" | grep -q "MS_PRIVATE\|remount-private"; then
        # MS_PRIVATE com overlay2 -> fallback automatico para vfs
        info "MS_PRIVATE detectado com driver ${cur_driver} -- a tentar fallback vfs..."
        log "MS_PRIVATE com driver=${cur_driver}: ${nest_err}"

        systemctl stop docker docker.socket containerd 2>/dev/null >> "$LOG" 2>&1 || true
        sleep 3
        rm -rf /var/lib/docker/* /var/lib/containerd/*
        mkdir -p /etc/docker
        printf '{\n  "storage-driver": "vfs"\n}\n' > /etc/docker/daemon.json
        systemctl start containerd >> "$LOG" 2>&1; sleep 3
        systemctl start docker     >> "$LOG" 2>&1; sleep 5
        cur_driver=$(docker info --format '{{.Driver}}' 2>/dev/null || echo "?")
        info "Storage driver apos fallback: ${cur_driver}"

        # Re-testar; se ainda MS_PRIVATE -> nesting mesmo nao activo
        nest_err=$(docker run --rm --pull=never hello-world 2>&1) || true
        if echo "$nest_err" | grep -q "MS_PRIVATE\|remount-private"; then
            _fail_nesting "$nest_err"
        fi
    fi

    if echo "$nest_err" | grep -q "ip_unprivileged_port_start"; then
        # Restricao sysctl do LXC -- nao e fatal porque docker-compose usa
        # privileged:true; apenas avisar o utilizador.
        _warn_sysctl_lxc "$nest_err"
    fi

    info "LXC OK -- Docker consegue correr contentores."
    log "check_docker_works: OK"
}

# -- Mostrar aviso Proxmox LXC sysctl (nao fatal) -------------------------------
# runc moderno tenta escrever net.ipv4.ip_unprivileged_port_start no namespace
# de rede de cada contentor; o LXC bloqueia essa escrita.
# O docker-compose ja usa privileged:true como workaround automatico.
# Esta funcao apenas avisa o utilizador da causa e da solucao "limpa" no host.
_warn_sysctl_lxc() {
    local detail="${1:-}"
    log "AVISO sysctl LXC: ${detail}"

    echo "" >&2
    echo "======================================================================" >&2
    echo "  AVISO: restricao sysctl no LXC Proxmox detectada" >&2
    echo "======================================================================" >&2
    echo "" >&2
    echo "  Causa: o runc nao consegue escrever 'net.ipv4.ip_unprivileged_port_start'" >&2
    echo "  no namespace de rede dos contentores (restricao do LXC Proxmox)." >&2
    echo "" >&2
    echo "  Workaround automatico: os servicos correm com 'privileged: true'" >&2
    echo "  (ja configurado no docker-compose.yml)." >&2
    echo "" >&2
    echo "  Solucao definitiva (sem privileged) -- NO HOST PROXMOX:" >&2
    echo "" >&2
    echo "    1. Ver o ID deste LXC:" >&2
    echo "         pct list" >&2
    echo "" >&2
    echo "    2. Editar o ficheiro de config do LXC (mudar XXX pelo ID):" >&2
    echo "         nano /etc/pve/lxc/XXX.conf" >&2
    echo "" >&2
    echo "    3. Adicionar a linha:" >&2
    echo "         lxc.sysctl.net.ipv4.ip_unprivileged_port_start = 0" >&2
    echo "" >&2
    echo "    4. Reiniciar o LXC:" >&2
    echo "         pct stop XXX && pct start XXX" >&2
    echo "" >&2
    echo "  Depois disso pode remover 'privileged: true' do docker-compose.yml." >&2
    echo "" >&2
    log "AVISO sysctl: privileged:true em uso como workaround"
}

# -- PASSO 3: Clonar repositorio ------------------------------------------------
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

# -- PASSO 4: Criar .env --------------------------------------------------------
step_create_env() {
    step "PASSO 4/5: Configurar variaveis de ambiente"

    # Gerar chave secreta Django automaticamente (50 caracteres alfanumericos)
    SECRET_KEY=$(openssl rand -base64 64 | tr -dc 'a-zA-Z0-9!@#%^&*(-_=+)' | head -c 50)
    log "SECRET_KEY gerada automaticamente."

    # Obter IP do servidor
    SERVER_IP=$(hostname -I 2>/dev/null | awk '{print $1}') || true
    [[ -z "$SERVER_IP" ]] && SERVER_IP="127.0.0.1"

    # Construir ALLOWED_HOSTS
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
# Em producao com HTTPS, adiciona a origem completa (ex: https://meusite.pt)
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

    # Actualizar listen do Nginx
    if [[ -f "$nginx_conf" ]]; then
        sed -i "s/listen 80;/listen ${APP_PORT};/" "$nginx_conf"
        log "Nginx configurado para porta ${APP_PORT}"
    fi

    # Actualizar mapeamento de porta no docker-compose.yml
    if [[ -f "$compose_file" ]]; then
        sed -i "s/\"80:80\"/\"${APP_PORT}:${APP_PORT}\"/" "$compose_file"
        log "docker-compose.yml actualizado para porta ${APP_PORT}"
    fi
}

# -- PASSO 5: Build e arranque dos servicos ------------------------------------
step_build_and_start() {
    step "PASSO 5/5: Compilar imagens Docker e iniciar servicos"

    info "ATENCAO: A compilacao da imagem Docker pode demorar varios minutos."
    info "Aguarde -- o progresso do build e mostrado abaixo:"
    echo ""

    cd "$APP_DIR"

    # Build explícito para mostrar progresso
    docker compose -f docker-compose.yml build              2>&1 | tee -a "$LOG"

    echo ""
    info "Build concluido. A iniciar servicos..."
    docker compose -f docker-compose.yml up -d              2>&1 | tee -a "$LOG"
    info "Todos os servicos iniciados."

    # Dar uns segundos para os containers arrancar e mostrar o estado
    sleep 5
    echo ""
    info "Estado dos contentores apos arranque:"
    docker compose -f docker-compose.yml ps                 2>&1 | tee -a "$LOG"
    echo ""
}

# -- Verificar saude dos servicos ----------------------------------------------
step_health_check() {
    info "A aguardar que todos os servicos fiquem operacionais..."
    local waited=0

    while true; do
        # Verificar se o Nginx/aplicacao responde na porta configurada
        if curl -sf "http://localhost:${APP_PORT}" > /dev/null 2>&1; then
            break
        fi
        # Verificar estado dos contentores
        local web_status
        web_status=$(docker inspect --format='{{.State.Status}}' stamps_web 2>/dev/null || echo "unknown")
        if [[ "$web_status" == "running" ]] && (( waited >= 30 )); then
            # Contentor a correr mas HTTP ainda nao responde -- aguardar mais um pouco
            :
        fi

        sleep 5; waited=$((waited + 5))
        printf "\r  Aguardar servicos... %ds" "$waited"

        if (( waited >= 120 )); then
            echo ""
            log "AVISO: Tempo esgotado -- servicos podem ainda estar a iniciar"
            info "AVISO: Aguarde 1-2 minutos e aceda a http://${SERVER_IP}:${APP_PORT}"
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
        # Substituir o APP_DIR no script de actualizacao pelo valor real
        sed -i "s|APP_DIR=\"/opt/mystamps\"|APP_DIR=\"${APP_DIR}\"|" "$dest"
        log "Script de actualizacao instalado em: ${dest}"
        info "Script de actualizacao instalado: mystamps-update"
    else
        log "AVISO: $src nao encontrado -- script de actualizacao nao instalado"
        info "AVISO: update.sh nao encontrado em $src"
    fi
}

# ==============================================================================
#   PROGRAMA PRINCIPAL
# ==============================================================================

# Inicializar log
: > "$LOG"
log "myStampsCollection Instalador v1.0 -- $(date)"
log "Repositorio: $REPO_URL"

# Verificar root
check_root

# Garantir que whiptail esta disponivel
ensure_whiptail

# Detectar SO
detect_os

# Ecra de boas-vindas
show_welcome

# Confirmacao
if ! confirm_install; then
    whiptail \
        --backtitle "myStampsCollection Installer  v1.0" \
        --title "Instalacao Cancelada" \
        --msgbox "Instalacao cancelada pelo utilizador.

Pode re-executar o instalador a qualquer momento:
  sudo bash install.sh" \
        10 54
    exit 0
fi

# Recolher configuracoes
ask_config

log "Configuracao: APP_DIR=$APP_DIR  PORT=$APP_PORT"

# -- Execucao com progresso no CLI ---------------------------------------------
echo ""
echo "======================================================================"
echo "  myStampsCollection -- Instalacao em curso"
echo "  ATENCAO: Este processo e demorado. Por favor aguarde."
echo "======================================================================"
echo ""

progress  5  "A actualizar sistema operativo..."
step_update_system

progress 20  "A instalar Docker CE..."
step_install_docker

progress 32  "A configurar storage driver (Proxmox LXC)..."
step_fix_lxc_overlay

progress 36  "A verificar compatibilidade Docker/LXC..."
check_docker_works

progress 45  "A descarregar repositorio..."
step_clone_repo

progress 55  "A criar configuracao (.env)..."
step_create_env

progress 60  "A configurar porta ${APP_PORT}..."
step_configure_port

progress 65  "A compilar e iniciar servicos (pode demorar)..."
step_build_and_start

progress 90  "A verificar disponibilidade da aplicacao..."
step_health_check

progress 95  "A instalar script de actualizacao..."
_install_update_script

progress 100 "Instalacao concluida!"

# -- Obter IP final e escrever resumo -----------------------------------------
_FINAL_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
[[ -z "$_FINAL_IP" ]] && _FINAL_IP="127.0.0.1"
_SUMMARY="/root/mystamps-access.txt"

printf '======================================================================\n'       > "$_SUMMARY"
printf '  myStampsCollection -- RESUMO DE ACESSO\n'                                   >> "$_SUMMARY"
printf '  Instalado em: %s\n' "$(date)"                                                >> "$_SUMMARY"
printf '======================================================================\n'       >> "$_SUMMARY"
printf '\n'                                                                             >> "$_SUMMARY"
printf '  Aplicacao  -->  http://%s:%s\n'  "$_FINAL_IP" "$APP_PORT"                   >> "$_SUMMARY"
printf '  Portainer  -->  http://%s:%s\n'  "$_FINAL_IP" "$PORTAINER_PORT"             >> "$_SUMMARY"
printf '\n'                                                                             >> "$_SUMMARY"
printf '  COMANDOS UTEIS:\n'                                                           >> "$_SUMMARY"
printf '    Actualizar:     mystamps-update\n'                                         >> "$_SUMMARY"
printf '    Ver logs web:   docker logs stamps_web -f\n'                               >> "$_SUMMARY"
printf '    Ver logs db:    docker logs stamps_db -f\n'                                >> "$_SUMMARY"
printf '    Ver logs nginx: docker logs stamps_nginx -f\n'                             >> "$_SUMMARY"
printf '    Parar:          docker compose -f %s/docker-compose.yml down\n' "$APP_DIR" >> "$_SUMMARY"
printf '    Reiniciar:      docker compose -f %s/docker-compose.yml restart\n' "$APP_DIR" >> "$_SUMMARY"
printf '    Log instalacao: %s\n' "$LOG"                                               >> "$_SUMMARY"
printf '\n'                                                                             >> "$_SUMMARY"
printf '======================================================================\n'       >> "$_SUMMARY"

# Imprimir no terminal
printf '\n'
printf '======================================================================\n'
printf '  myStampsCollection -- INSTALACAO CONCLUIDA!\n'
printf '======================================================================\n'
printf '\n'
printf '  Aplicacao  -->  http://%s:%s\n'  "$_FINAL_IP" "$APP_PORT"
printf '  Portainer  -->  http://%s:%s\n'  "$_FINAL_IP" "$PORTAINER_PORT"
printf '\n'
printf '  Para actualizar no futuro: mystamps-update\n'
printf '  (Resumo guardado em: %s)\n' "$_SUMMARY"
printf '\n'
printf '======================================================================\n'
printf '\n'

log "=== Instalacao concluida em $(date) ==="
exit 0
