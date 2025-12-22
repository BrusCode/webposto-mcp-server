#!/usr/bin/env python3
"""
WebPosto MCP Server - Modo HTTP/SSE
Quality Automação

Este módulo executa o servidor MCP em modo HTTP para acesso remoto.
Utiliza o transporte 'sse' (Server-Sent Events) para comunicação.

Configuração de host/port via variáveis de ambiente ou diretamente no código.

Uso:
  python -m src.server_http

Ou com uvicorn diretamente:
  uvicorn src.server_http:app --host 0.0.0.0 --port 8000
"""

import sys
import os

# Adicionar o diretório pai ao path para importar o módulo server
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.server import mcp, API_KEY, WEBPOSTO_BASE_URL, logger

# Configurar o servidor para aceitar conexões externas
# O FastMCP usa Settings para configurar host/port
mcp.settings.host = os.getenv("MCP_HOST", "0.0.0.0")
mcp.settings.port = int(os.getenv("MCP_PORT", "8000"))

# Configurar segurança de transporte para permitir acesso externo
# Por padrão, o FastMCP só permite localhost
mcp.settings.transport_security.enable_dns_rebinding_protection = False
mcp.settings.transport_security.allowed_hosts = ["*"]
mcp.settings.transport_security.allowed_origins = ["*"]

# Exportar o app ASGI para uso com uvicorn
# O FastMCP cria internamente uma aplicação Starlette
app = mcp.sse_app()


def main():
    """Ponto de entrada para o servidor MCP em modo HTTP/SSE."""
    if not API_KEY:
        logger.error("=" * 60)
        logger.error("ERRO: WEBPOSTO_API_KEY não configurada!")
        logger.error("Defina a variável de ambiente WEBPOSTO_API_KEY")
        logger.error("=" * 60)
        sys.exit(1)
    
    logger.info("=" * 60)
    logger.info("WebPosto MCP Server - Quality Automação v1.3.0")
    logger.info("Modo: HTTP/SSE (Acesso Remoto)")
    logger.info("=" * 60)
    logger.info(f"URL Base API: {WEBPOSTO_BASE_URL}")
    logger.info(f"Chave API: {'*' * 8}...{API_KEY[-8:] if len(API_KEY) > 8 else '****'}")
    logger.info(f"Host: {mcp.settings.host}")
    logger.info(f"Port: {mcp.settings.port}")
    logger.info(f"Endpoint SSE: http://{mcp.settings.host}:{mcp.settings.port}/sse")
    logger.info("=" * 60)
    
    # Executar em modo SSE (Server-Sent Events)
    mcp.run(transport="sse")


if __name__ == "__main__":
    main()
