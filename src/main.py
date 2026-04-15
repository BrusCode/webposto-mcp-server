#!/usr/bin/env python3
"""
WebPosto MCP Server — Ponto de Entrada Alternativo (HTTP/SSE)
Quality Automação

Este módulo é um atalho para iniciar o servidor no modo HTTP/SSE.
Para o modo padrão (stdio, compatível com Claude Desktop), use:

    python -m src.server

Para o modo HTTP/SSE (acesso remoto via rede), use:

    python -m src.server_http

ou execute este módulo diretamente:

    python -m src.main

Ver também:
    - src/server.py      : servidor MCP principal (stdio)
    - src/server_http.py : modo HTTP/SSE
    - docs/DEPLOY_PORTAINER.md : deploy em containers
"""

from src.server_http import main

if __name__ == "__main__":
    main()
