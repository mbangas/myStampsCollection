# 📮 myStampsCollection — Guia de Instalação

> **Para toda a gente** — Este guia foi escrito para qualquer pessoa, mesmo sem conhecimentos técnicos. Siga os passos na ordem indicada e a aplicação ficará pronta a usar.

---

## O que é o myStampsCollection?

O **myStampsCollection** é uma plataforma web open source para colecionadores de selos filatélicos. Permite catalogar selos por país, gerir a sua coleção pessoal, registar repetidos e variantes, e propor trocas com outros utilizadores.

---

## O que o instalador faz?

O instalador executa automaticamente, sem necessidade de saber programar:

| Passo | O que acontece |
|-------|---------------|
| **1** | Actualiza o sistema operativo (instala as últimas actualizações de segurança) |
| **2** | Instala o **Docker** — o motor que executa a aplicação em contentores isolados |
| **3** | Descarrega o código do **myStampsCollection** do GitHub |
| **4** | Cria o ficheiro de configuração (`.env`) com as credenciais fornecidas |
| **5** | Compila e inicia todos os serviços (Django, PostgreSQL, Nginx) |

---

## Antes de começar — Requisitos

### Onde instalar?

O instalador foi criado para ser executado num **LXC no Proxmox** acabado de criar.  
Funciona com as seguintes versões:

| Sistema Operativo | Versão Recomendada |
|------------------|--------------------|
| **Debian** ✅ *(recomendado)* | 12 (Bookworm) |
| **Debian** | 11 (Bullseye) |
| **Ubuntu** | 22.04 LTS (Jammy) |
| **Ubuntu** | 24.04 LTS (Noble) |

> 💡 **Recomendação:** Use **Debian 12** — é a opção mais leve e estável para servidores.

---

### Criar o LXC no Proxmox

1. No Proxmox, vá a **Create CT** (Criar Contentor)
2. Escolha o template **Debian 12** (ou Ubuntu 22.04)
3. Defina recursos mínimos recomendados:
   - **CPU:** 2 núcleos
   - **RAM:** 1024 MB (1 GB)
   - **Disco:** 20 GB
4. Ative a opção **"Nesting"** nas funcionalidades (necessário para Docker dentro do LXC):
   - Em *Options → Features → Nesting* → marque a caixa
5. Inicie o LXC e aceda à consola

---

### Acesso ao LXC

Pode aceder ao LXC de duas formas:

- **Consola do Proxmox** — clique no LXC e depois em "Console"
- **SSH** — `ssh root@<IP-do-LXC>`

---

## Instalação — Passo a Passo

### 1. Aceder ao LXC

Abra a consola do LXC (no Proxmox) ou ligue via SSH:

```bash
ssh root@<IP-do-LXC>
```

> Substitua `<IP-do-LXC>` pelo endereço IP do seu LXC (visível no Proxmox).

---

### 2. Descarregar o instalador

Execute este comando para descarregar o instalador directamente do GitHub:

```bash
curl -fsSL https://raw.githubusercontent.com/mbangas/myStampsCollection/master/setup/install.sh -o install.sh
```

---

### 3. Executar o instalador

```bash
sudo bash install.sh
```

> Se já estiver como `root`, basta `bash install.sh`.

---

### 4. Seguir o assistente de instalação

O instalador abre um **ecrã azul interactivo** que o guia em cada passo:

#### Ecrã 1 — Boas-vindas
Apresenta o nome da solução e o resumo do que vai ser instalado. Prima **OK** para continuar.

#### Ecrã 2 — Confirmação
Confirme que pretende prosseguir com a instalação. Prima **Sim**.

#### Ecrã 3 — Porta da Aplicação
Define em que porta a aplicação ficará disponível.  
**Deixe o valor padrão `80`** salvo se tiver um motivo específico para mudar.

#### Ecrã 4 — Directório de Instalação
Pasta onde o código será descarregado.  
**Deixe o valor padrão `/opt/mystamps`** salvo indicação contrária.

#### Ecrã 5 — Password da Base de Dados
Introduza uma password segura para a base de dados PostgreSQL.

> ⚠️ **Importante:** Use uma password forte (mínimo 8 caracteres). Esta password é guardada no ficheiro `.env` dentro do directório de instalação.

#### Ecrã 6 — Barra de Progresso
O instalador executa todos os passos automaticamente mostrando o progresso em tempo real. **Não é necessário fazer nada** — aguarde até a barra chegar a 100%.

O instalador v2.0 inclui **self-healing automático**: se detectar problemas com o Docker em Proxmox LXC (sysctl, storage driver, nesting), tenta corrigir automaticamente sem intervenção.

> ⏱️ A instalação demora tipicamente **5 a 15 minutos** dependendo da velocidade da ligação à Internet.

---

### 5. Instalação concluída!

No final da instalação é apresentado o URL de acesso:

```
======================================================================
  myStampsCollection -- INSTALACAO CONCLUIDA!
======================================================================

  Aplicacao  -->  http://<IP-do-servidor>:80

  Para actualizar no futuro: mystamps-update
  (Resumo guardado em: /root/mystamps-access.txt)
======================================================================
```

---

## Primeiro acesso à aplicação

### Abrir no browser

Abra o browser e aceda a:

```
http://<IP-do-servidor>
```

> Substitua `<IP-do-servidor>` pelo IP do seu LXC.

### Criar a conta de administrador

Na primeira visita, registe-se na aplicação:

1. Clique em **Registar** no menu
2. Preencha o formulário com o seu nome de utilizador, e-mail e password
3. Após o registo, aceda ao painel de administração em `http://<IP>/admin/` para gerir utilizadores

> Para ter acesso de administrador, execute o seguinte comando única vez:
> ```bash
> docker exec -it stamps_web python manage.py createsuperuser
> ```

---

## Como aceder à aplicação

### 📮 myStampsCollection (A aplicação)

| Endereço | Descrição |
|----------|-----------|
| `http://<IP>` | Página principal |
| `http://<IP>/catalogo/` | Catálogo de selos por país |
| `http://<IP>/colecao/` | Gestão da coleção pessoal |
| `http://<IP>/trocas/` | Zona de trocas entre utilizadores |
| `http://<IP>/admin/` | Painel de administração Django |

---

## Comandos úteis (na linha de comando)

Se precisar de gerir a aplicação depois da instalação:

```bash
# Ver os logs da aplicação web em tempo real
docker logs stamps_web -f

# Ver os logs da base de dados
docker logs stamps_db -f

# Ver os logs do Nginx
docker logs stamps_nginx -f

# Parar todos os serviços
docker compose -f /opt/mystamps/docker-compose.yml down

# Reiniciar todos os serviços
docker compose -f /opt/mystamps/docker-compose.yml restart

# Actualizar para a versão mais recente
mystamps-update

# Ver o estado dos contentores
docker ps

# Executar um comando Django dentro do contentor
docker exec -it stamps_web python manage.py <comando>

# Criar superutilizador manualmente
docker exec -it stamps_web python manage.py createsuperuser

# Ver quanto espaço os volumes ocupam
docker system df
```

---

## Fazer backup dos dados

Os dados persistentes estão em volumes Docker geridos automaticamente.  
Para fazer um backup completo:

```bash
# Backup da base de dados PostgreSQL
docker exec stamps_db pg_dump -U stamps_user mystamps_db \
  > mystamps_backup_$(date +%Y%m%d).sql

# Backup dos ficheiros de media (imagens de selos)
docker run --rm \
  -v mystamps_media_data:/data \
  -v $(pwd):/backup \
  alpine tar czf /backup/mystamps_media_$(date +%Y%m%d).tar.gz /data
```

Guarde estes ficheiros num local seguro (outro disco, cloud, etc.).

### Restaurar a base de dados

```bash
# Restaurar um backup SQL
docker exec -i stamps_db psql -U stamps_user mystamps_db \
  < mystamps_backup_YYYYMMDD.sql
```

---

## Resolução de problemas

### A barra de progresso parou / erro durante a instalação

Consulte o log de instalação que foi gerado:

```bash
cat /tmp/mystamps_install_*.log
```

### Não consigo aceder à aplicação no browser

1. Verifique se os contentores estão a correr: `docker ps`
2. Verifique os logs: `docker logs stamps_web`
3. Confirme que a porta 80 não está bloqueada pela firewall do Proxmox

### A aplicação abre mas fica a carregar

Aguarde 30-60 segundos e recarregue a página. Na primeira inicialização, a aplicação:
- Aplica as migrações da base de dados
- Recolhe os ficheiros estáticos
- Carrega o catálogo inicial de selos (fixtures)

### Erro "ip_unprivileged_port_start: permission denied"

Este erro ocorre em LXC Proxmox quando o kernel bloqueia a escrita de sysctls. O instalador v2.0 tenta corrigir automaticamente via três mecanismos:

1. **sysctl no host LXC** — define `net.ipv4.ip_unprivileged_port_start=0`
2. **Sem `privileged: true`** — o docker-compose.yml não usa contentores privilegiados
3. **Fallback `network_mode: host`** — como último recurso, elimina o namespace de rede

Se o self-healing não resolver, no **host Proxmox**:

```bash
# Editar a configuração do LXC (substituir XXX pelo ID)
nano /etc/pve/lxc/XXX.conf

# Adicionar esta linha:
lxc.sysctl.net.ipv4.ip_unprivileged_port_start = 0

# Reiniciar o LXC
pct stop XXX && pct start XXX
```

### Erro "MS_PRIVATE: permission denied"

Este erro indica que o LXC não tem **nesting** activo. O instalador tenta mudar automaticamente o storage driver para `vfs`. Se falhar:

No **host Proxmox**:
```bash
pct set XXX --features nesting=1,keyctl=1
pct stop XXX && pct start XXX
```

Ou na interface Proxmox: Container → Options → Features → activar **Nesting**.

Este processo pode demorar 1-2 minutos na primeira vez.

### Erro "502 Bad Gateway" no Nginx

O contentor Django ainda está a iniciar. Aguarde e tente novamente.

### Preciso de reinstalar

```bash
# Parar e remover os contentores (os volumes de dados NAO sao apagados)
docker compose -f /opt/mystamps/docker-compose.yml down
docker rmi $(docker images | grep mystamps | awk '{print $3}') 2>/dev/null || true

# Re-executar o instalador
sudo bash install.sh
```

---

## Estrutura criada após instalação

```
/opt/mystamps/              ← Código da aplicação (git clone)
  ├── manage.py
  ├── requirements.txt
  ├── Dockerfile
  ├── docker-compose.yml
  ├── .env                  ← Configuração gerada pelo instalador (não apagar!)
  ├── stamps_config/        ← Definições Django
  ├── src/                  ← Código das aplicações
  │   ├── accounts/         ← Utilizadores e perfis
  │   ├── catalog/          ← Países, selos e catálogo
  │   ├── collection/       ← Coleção do utilizador
  │   └── exchange/         ← Trocas entre utilizadores
  ├── docker/
  │   ├── entrypoint.sh     ← Script de arranque do contentor
  │   └── nginx/            ← Configuração do Nginx
  └── setup/
      ├── install.sh        ← Este instalador
      ├── update.sh         ← Script de actualização
      └── INSTALL.md        ← Este guia

Volumes Docker geridos automaticamente:
  mystamps_postgres_data    ← Base de dados PostgreSQL (⭐ fazer backups!)
  mystamps_media_data       ← Imagens e ficheiros carregados
  mystamps_static_data      ← Ficheiros estáticos Django
```

---

## Informação técnica (opcional)

| Componente | Versão | Porta |
|-----------|--------|-------|
| **myStampsCollection** | 1.0 | 80 |
| **Django** | 5.0 | — |
| **Python** (dentro do Docker) | 3.12 | — |
| **PostgreSQL** | 16 Alpine | 5432 (interno) |
| **Gunicorn** | 21.2 | 8000 (interno) |
| **Nginx** | 1.27 Alpine | 80 |
| **Docker CE** | última estável | — |

O instalador é compatível com **Debian 11/12** e **Ubuntu 22.04/24.04** e detecta automaticamente qual o sistema para usar o repositório Docker correcto.

---

<div align="center">

**📮 myStampsCollection** · Coleções de Selos Filatélicos  
[GitHub](https://github.com/mbangas/myStampsCollection)

</div>
