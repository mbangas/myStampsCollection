# ─── Imagem base ─────────────────────────────────────────────────────────────
FROM python:3.12-slim AS base

# Variáveis de ambiente que evitam ficheiros .pyc e tornam o output imediato
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=stamps_config.settings

WORKDIR /app

# ─── Dependências do SO ───────────────────────────────────────────────────────
# libpq-dev: necessário para o psycopg2-binary
# gettext:   necessário para o makemessages do Django (i18n)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gettext \
    && rm -rf /var/lib/apt/lists/*

# ─── Stage: builder (instala os pacotes Python) ───────────────────────────────
FROM base AS builder

COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# ─── Stage: runtime ───────────────────────────────────────────────────────────
FROM base AS runtime

# Copia os pacotes instalados do stage builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copia o código da aplicação
COPY . .

# Cria directórios para media e staticfiles e ajusta permissões
RUN mkdir -p /app/media /app/staticfiles \
    && useradd -m -u 1000 appuser \
    && chown -R appuser:appuser /app

# ─── Entrypoint ───────────────────────────────────────────────────────────────
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

USER appuser

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
