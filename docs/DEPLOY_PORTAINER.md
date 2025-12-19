# Deploy via Portainer - WebPosto MCP Server

Este guia detalha como fazer o deploy do WebPosto MCP Server usando o Portainer.

## Sumário

- [Pré-requisitos](#pré-requisitos)
- [Método 1: Deploy Direto (Recomendado)](#método-1-deploy-direto-recomendado)
- [Método 2: Deploy com Build Local](#método-2-deploy-com-build-local)
- [Configuração de Variáveis](#configuração-de-variáveis)
- [Verificação do Deploy](#verificação-do-deploy)
- [Troubleshooting](#troubleshooting)

---

## Pré-requisitos

- **Portainer** instalado e configurado (versão 2.x ou superior)
- **Docker** ou **Docker Swarm** no ambiente de destino
- **Chave de API** do WebPosto (obtenha no painel administrativo)

---

## Método 1: Deploy Direto (Recomendado)

Este método usa uma imagem base do Python e clona o repositório automaticamente.

### Passo 1: Acessar o Portainer

1. Acesse o Portainer (ex: `https://seu-servidor:9443`)
2. Faça login com suas credenciais

### Passo 2: Criar a Stack

1. No menu lateral, clique em **Stacks**
2. Clique em **+ Add Stack**
3. Preencha:
   - **Name:** `webposto-mcp`
   - **Build method:** Web editor

### Passo 3: Colar o Conteúdo da Stack

Cole o seguinte conteúdo no editor:

```yaml
version: "3.8"

services:
  webposto-mcp:
    image: python:3.11-slim
    container_name: webposto-mcp-server
    restart: unless-stopped
    working_dir: /app
    command: >
      bash -c "
        pip install --no-cache-dir requests mcp pydantic pydantic-settings python-dotenv httpx &&
        git clone https://github.com/BrusCode/webposto-mcp-server.git /app/repo 2>/dev/null || (cd /app/repo && git pull) &&
        cd /app/repo &&
        python -m src.server
      "
    environment:
      - WEBPOSTO_API_KEY=${WEBPOSTO_API_KEY}
      - WEBPOSTO_URL=${WEBPOSTO_URL:-https://web.qualityautomacao.com.br}
      - WEBPOSTO_EMPRESA_CODIGO=${WEBPOSTO_EMPRESA_CODIGO:-}
      - LOG_LEVEL=${LOG_LEVEL:-INFO}
      - PYTHONUNBUFFERED=1
      - PYTHONPATH=/app/repo
    volumes:
      - webposto-data:/app/repo
      - webposto-logs:/app/logs
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 512M
    healthcheck:
      test: ["CMD", "python", "-c", "import sys; sys.exit(0)"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "5"
    networks:
      - webposto-network

volumes:
  webposto-data:
  webposto-logs:

networks:
  webposto-network:
    driver: bridge
```

### Passo 4: Configurar Variáveis de Ambiente

Role para baixo até a seção **Environment variables** e adicione:

| Nome | Valor | Obrigatório |
|------|-------|-------------|
| `WEBPOSTO_API_KEY` | `sua-chave-api-aqui` | ✅ Sim |
| `WEBPOSTO_URL` | `https://web.qualityautomacao.com.br` | Não |
| `WEBPOSTO_EMPRESA_CODIGO` | `7` | Não |
| `LOG_LEVEL` | `INFO` | Não |

### Passo 5: Deploy

1. Clique em **Deploy the stack**
2. Aguarde a criação do container
3. Verifique o status em **Containers**

---

## Método 2: Deploy com Build Local

Use este método se você clonou o repositório localmente e quer fazer o build da imagem.

### Passo 1: Clonar o Repositório

```bash
git clone https://github.com/BrusCode/webposto-mcp-server.git
cd webposto-mcp-server
```

### Passo 2: Configurar Variáveis

```bash
cp .env.example .env
nano .env  # Edite e adicione sua WEBPOSTO_API_KEY
```

### Passo 3: Deploy via Portainer

1. No Portainer, vá em **Stacks** > **+ Add Stack**
2. **Name:** `webposto-mcp`
3. **Build method:** Upload
4. Faça upload do arquivo `docker-stack-build.yml`
5. Configure as variáveis de ambiente
6. Clique em **Deploy the stack**

### Alternativa: Deploy via CLI

```bash
docker-compose -f docker-stack-build.yml up -d --build
```

---

## Configuração de Variáveis

### Variáveis Obrigatórias

| Variável | Descrição | Exemplo |
|----------|-----------|---------|
| `WEBPOSTO_API_KEY` | Chave de autenticação da API | `2939647d-74d6-4bd2-b2b6-720e899c8187` |

### Variáveis Opcionais

| Variável | Descrição | Padrão |
|----------|-----------|--------|
| `WEBPOSTO_URL` | URL base da API | `https://web.qualityautomacao.com.br` |
| `WEBPOSTO_EMPRESA_CODIGO` | Código da empresa padrão | (vazio) |
| `LOG_LEVEL` | Nível de log | `INFO` |

---

## Verificação do Deploy

### Via Portainer

1. Vá em **Containers**
2. Localize `webposto-mcp-server`
3. Verifique o status (deve estar **Running**)
4. Clique no container para ver os logs

### Via CLI

```bash
# Ver status
docker ps | grep webposto

# Ver logs
docker logs webposto-mcp-server -f

# Ver logs das últimas 100 linhas
docker logs webposto-mcp-server --tail 100
```

### Logs Esperados

```
2025-12-19 17:30:00 - __main__ - INFO - ============================================================
2025-12-19 17:30:00 - __main__ - INFO - WebPosto MCP Server - Quality Automação v1.2.0
2025-12-19 17:30:00 - __main__ - INFO - ============================================================
2025-12-19 17:30:00 - __main__ - INFO - URL Base: https://web.qualityautomacao.com.br
2025-12-19 17:30:00 - __main__ - INFO - Chave API: ********...899c8187
2025-12-19 17:30:00 - __main__ - INFO - ============================================================
```

---

## Troubleshooting

### Erro: Container não inicia

**Causa:** Variável `WEBPOSTO_API_KEY` não configurada.

**Solução:** Verifique se a variável foi adicionada corretamente nas configurações da stack.

### Erro: Timeout na API

**Causa:** Rede ou firewall bloqueando acesso à API.

**Solução:** 
1. Verifique se o container tem acesso à internet
2. Teste: `docker exec webposto-mcp-server curl -I https://web.qualityautomacao.com.br`

### Erro: Módulo não encontrado

**Causa:** Dependências não instaladas corretamente.

**Solução:** Recrie o container:
```bash
docker-compose -f docker-stack.yml down
docker-compose -f docker-stack.yml up -d --build
```

### Ver Logs Detalhados

```bash
# Logs em tempo real
docker logs webposto-mcp-server -f

# Logs com timestamps
docker logs webposto-mcp-server -t

# Últimas 50 linhas
docker logs webposto-mcp-server --tail 50
```

---

## Atualização

Para atualizar o servidor para a versão mais recente:

### Via Portainer

1. Vá em **Stacks** > `webposto-mcp`
2. Clique em **Editor**
3. Clique em **Update the stack**
4. Marque **Re-pull image and redeploy**
5. Clique em **Update**

### Via CLI

```bash
docker-compose -f docker-stack.yml pull
docker-compose -f docker-stack.yml up -d
```

---

## Suporte

- **Documentação:** [GitHub - webposto-mcp-server](https://github.com/BrusCode/webposto-mcp-server)
- **Issues:** [GitHub Issues](https://github.com/BrusCode/webposto-mcp-server/issues)
- **Quality Automação:** [qualityautomacao.com.br](https://www.qualityautomacao.com.br)
