# myStampsCollection 🌍📮

Sistema web para gerir coleções de selos filatélicos de todo o mundo, com catálogo por país, gestão de coleção pessoal e zona de trocas entre utilizadores.

## Funcionalidades

| Módulo | Descrição |
|---|---|
| **Catálogo** | Navega selos organizados por país, com filtros por tema e ano |
| **Coleção** | Regista os selos que tens, quantidades e repetidos |
| **Indicadores** | Estatísticas da tua coleção (totais, países, repetidos) |
| **Trocas** | Propõe e aceita trocas com outros colecionadores |
| **Matches** | Algoritmo automático que encontra trocas compatíveis |

## Tecnologias

- **Backend**: Django 5 + Python 3.11+
- **Base de dados**: PostgreSQL
- **Frontend**: Bootstrap 5 + Bootstrap Icons
- **Uploads**: Pillow (imagens de selos e bandeiras)
- **Formulários**: django-crispy-forms + crispy-bootstrap5

## Início Rápido

### 1. Pré-requisitos

- Python 3.11+
- PostgreSQL (em execução)

### 2. Clonar e configurar o ambiente

```bash
# Criar e activar ambiente virtual
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # macOS/Linux

# Instalar dependências
pip install -r requirements.txt
```

### 3. Configurar variáveis de ambiente

```bash
# Copiar o ficheiro de exemplo
copy .env.example .env          # Windows
cp .env.example .env            # macOS/Linux

# Editar .env com os teus dados de ligação PostgreSQL
```

### 4. Criar a base de dados

```sql
-- No psql ou pgAdmin:
CREATE DATABASE mystamps_db;
```

### 5. Aplicar migrações

```bash
python manage.py migrate
```

### 6. Criar superutilizador (admin)

```bash
python manage.py createsuperuser
```

### 7. Popular com dados de exemplo (opcional)

```bash
python tools/popular_bd.py
```

### 8. Iniciar o servidor

```bash
python manage.py runserver
```

Acede a **http://127.0.0.1:8000** para abrir a aplicação.  
O painel de administração está em **http://127.0.0.1:8000/admin/**.

## Estrutura do Projeto

```
myStampsCollection/
├── manage.py
├── requirements.txt
├── .env.example
├── stamps_config/          # Configurações Django
│   ├── settings.py
│   └── urls.py
├── src/
│   ├── accounts/           # Utilizadores e perfis
│   ├── catalog/            # Países, selos e temas
│   ├── collection/         # Coleção do utilizador
│   ├── exchange/           # Trocas entre utilizadores
│   ├── static/
│   │   ├── css/main.css
│   │   └── js/main.js
│   └── templates/          # Templates HTML
├── css/                    # CSS adicional (STATICFILES_DIRS)
├── media/                  # Uploads (criado em runtime)
└── tools/
    └── popular_bd.py       # Script de dados de exemplo
```

## Modelos de Dados

```
Pais ──< Selo >── Tema
           │
     ItemColecao >── Utilizador
           │                │
     OfertaTroca            └─ PerfilUtilizador
     PedidoTroca
           │
         Troca (iniciador ↔ receptor)
```

## Licença

MIT

