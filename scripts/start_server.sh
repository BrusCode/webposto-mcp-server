#!/bin/bash
# =============================================================================
# WebPosto MCP Server - Script de Inicialização
# Quality Automação
# =============================================================================

set -e

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Diretório do script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  WebPosto MCP Server - Quality Automação${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Verificar se o arquivo .env existe
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo -e "${YELLOW}Arquivo .env não encontrado.${NC}"
    echo -e "${YELLOW}Criando a partir de .env.example...${NC}"
    
    if [ -f "$PROJECT_DIR/.env.example" ]; then
        cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
        echo -e "${RED}ATENÇÃO: Configure sua API_KEY no arquivo .env${NC}"
        exit 1
    else
        echo -e "${RED}Erro: .env.example não encontrado${NC}"
        exit 1
    fi
fi

# Carregar variáveis de ambiente
source "$PROJECT_DIR/.env"

# Verificar se a API_KEY está configurada
if [ -z "$WEBPOSTO_API_KEY" ] || [ "$WEBPOSTO_API_KEY" = "SUA_API_KEY_AQUI" ]; then
    echo -e "${RED}Erro: WEBPOSTO_API_KEY não configurada no arquivo .env${NC}"
    exit 1
fi

# Verificar Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Erro: Python 3 não encontrado${NC}"
    echo "Instale Python 3.10 ou superior"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo -e "Python versão: ${GREEN}$PYTHON_VERSION${NC}"

# Verificar/criar ambiente virtual
VENV_DIR="$PROJECT_DIR/.venv"
if [ ! -d "$VENV_DIR" ]; then
    echo -e "${YELLOW}Criando ambiente virtual...${NC}"
    python3 -m venv "$VENV_DIR"
fi

# Ativar ambiente virtual
source "$VENV_DIR/bin/activate"

# Instalar dependências
echo -e "${YELLOW}Verificando dependências...${NC}"
pip install -q -r "$PROJECT_DIR/requirements.txt"

# Iniciar servidor
echo ""
echo -e "${GREEN}Iniciando servidor MCP...${NC}"
echo -e "URL da API: ${WEBPOSTO_URL:-https://web.qualityautomacao.com.br/INTEGRACAO}"
echo ""

cd "$PROJECT_DIR"
python -m src.server
