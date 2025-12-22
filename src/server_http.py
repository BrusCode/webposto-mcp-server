#!/usr/bin/env python3
"""
WebPosto MCP Server - Modo HTTP/SSE
Quality Automação

Este módulo executa o servidor MCP em modo HTTP para acesso remoto via Traefik.
Endpoint padrão: https://mcp.qualityautomacao.com.br/mcp
"""

import sys
import os

# Adicionar o diretório pai ao path para importar o módulo server
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.server import mcp, API_KEY, WEBPOSTO_BASE_URL, logger

def main():
    """Ponto de entrada para o servidor MCP em modo HTTP."""
    if not API_KEY:
        logger.error("=" * 60)
        logger.error("ERRO: WEBPOSTO_API_KEY não configurada!")
        logger.error("Defina a variável de ambiente WEBPOSTO_API_KEY")
        logger.error("=" * 60)
        sys.exit(1)
    
    logger.info("=" * 60)
    logger.info("WebPosto MCP Server - Quality Automação v1.2.0")
    logger.info("Modo: HTTP/SSE (Acesso Remoto)")
    logger.info("=" * 60)
    logger.info(f"URL Base API: {WEBPOSTO_BASE_URL}")
    logger.info(f"Chave API: {'*' * 8}...{API_KEY[-8:] if len(API_KEY) > 8 else '****'}")
    logger.info("Endpoint MCP: http://0.0.0.0:8000/mcp")
    logger.info("=" * 60)
    
    # Executar em modo HTTP na porta 8000
    mcp.run(transport="http", host="0.0.0.0", port=8000)

if __name__ == "__main__":
    main()
