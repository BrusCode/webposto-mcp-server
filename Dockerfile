# =============================================================================
# WebPosto MCP Server - Dockerfile
# Quality Automação
# =============================================================================

# Estágio de build
FROM python:3.11-slim as builder

WORKDIR /app

# Instalar dependências de build
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements e instalar dependências
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# =============================================================================
# Estágio de produção
# =============================================================================
FROM python:3.11-slim as production

WORKDIR /app

# Criar usuário não-root para segurança
RUN groupadd -r webposto && useradd -r -g webposto webposto

# Copiar dependências instaladas do estágio de build
COPY --from=builder /root/.local /home/webposto/.local

# Copiar código fonte
COPY --chown=webposto:webposto . .

# Configurar PATH para incluir pacotes do usuário
ENV PATH=/home/webposto/.local/bin:$PATH
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Variáveis de ambiente padrão (devem ser sobrescritas em runtime)
ENV WEBPOSTO_URL=https://web.qualityautomacao.com.br/INTEGRACAO
ENV WEBPOSTO_API_KEY=""

# Trocar para usuário não-root
USER webposto

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health', timeout=5)" || exit 1

# Expor porta (para modo HTTP, se aplicável)
EXPOSE 8000

# Comando padrão - executa o servidor MCP via stdio
CMD ["python", "-m", "src.server"]
