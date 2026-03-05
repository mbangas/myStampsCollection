# myStampsCollection

> Sistema web para gerir coleções de selos filatélicos de todo o mundo, com catálogo por país, gestão de coleção pessoal e zona de trocas entre utilizadores.

![Build Status](https://img.shields.io/badge/build-passing-brightgreen)
![Version](https://img.shields.io/badge/version-1.0-blue)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

## O que é?

myStampsCollection é uma plataforma open source para colecionadores de selos:
- Catálogo internacional por país, tema e ano
- Gestão de coleção pessoal, incluindo repetidos e variantes
- Algoritmo de "matches" para trocas automáticas entre utilizadores
- Estatísticas detalhadas da coleção
- Importação fácil de dados via CSV

## Por que usar?

- Organize e visualize sua coleção de selos de forma intuitiva
- Encontre facilmente selos que faltam e repetidos
- Proponha e aceite trocas com outros colecionadores
- Sistema extensível e fácil de contribuir
- Suporte a importação de catálogos nacionais

## Como começar

### Pré-requisitos
- Python 3.11+
- PostgreSQL
- Docker (opcional, recomendado para produção)

### Instalação rápida

```bash
# Clone o repositório
$ git clone https://github.com/mbangas/myStampsCollection.git
$ cd myStampsCollection

# Crie e ative o ambiente virtual
$ python -m venv .venv
$ source .venv/bin/activate

# Instale as dependências
$ pip install -r requirements.txt
```

### Configuração

1. Copie o arquivo de exemplo de ambiente:
      ```bash
      cp .env.example .env
      ```
2. Edite `.env` com os dados do seu PostgreSQL
3. Crie a base de dados:
      ```sql
      CREATE DATABASE mystamps_db;
      ```
4. Aplique as migrações:
      ```bash
      python manage.py migrate
      ```
5. Crie um superusuário:
      ```bash
      python manage.py createsuperuser
      ```
6. (Opcional) Popule com dados de exemplo:
      ```bash
      python tools/popular_bd.py
      ```
7. Inicie o servidor:
      ```bash
      python manage.py runserver
      ```

Acesse [http://127.0.0.1:8000](http://127.0.0.1:8000) para usar a aplicação.

### Usando com Docker

```bash
# Suba todos os serviços (web, db, nginx)
$ docker compose up --build
```

Acesse [http://localhost](http://localhost) no navegador.

## Estrutura do Projeto

```
myStampsCollection/
├── manage.py
├── requirements.txt
├── stamps_config/          # Configurações Django
├── src/
│   ├── accounts/           # Utilizadores e perfis
│   ├── catalog/            # Países, selos e temas
│   ├── collection/         # Coleção do utilizador
│   ├── exchange/           # Trocas entre utilizadores
│   ├── static/             # CSS/JS
│   └── templates/          # HTML
├── tools/                  # Scripts utilitários
├── docs/                   # Documentação e dados de catálogo
├── docker/                 # Configuração Docker/Nginx
```

Mais detalhes em [docs/README.md](docs/README.md).

## Atualizações

Para atualizar dependências:
```bash
pip install -r requirements.txt --upgrade
```
Para atualizar o projeto:
```bash
git pull origin master
```

## Onde obter ajuda

- [Documentação](docs/README.md)
- [Exemplo de dados](docs/Portugal/selos.csv)
- [Scripts utilitários](tools/)
- [Wiki do projeto](docs/README.md)

## Quem mantém e contribui

- Mantido por [mbangas](https://github.com/mbangas)
- Contribuições são bem-vindas! Veja [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) para diretrizes
- Relate problemas ou sugestões via Issues no GitHub

---

> **Nota:** Este projeto é open source sob licença MIT. Veja o arquivo [LICENSE](LICENSE) para detalhes.
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

