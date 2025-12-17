#!/usr/bin/env python3

import logging
import sys
from fastapi import FastAPI
from mcp.server.fastmcp import FastMCP

# Configuração de logging
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger(__name__)

# Criação do servidor MCP
mcp = FastMCP(
    server_name="webposto-mcp",
    server_title="WebPosto MCP Server",
    server_description="Servidor MCP para integração com o sistema de gestão de postos WebPosto.",
    tools_package="src.tools" # Pacote onde as ferramentas serão descobertas
)

# Criação da aplicação FastAPI
app = FastAPI(
    title="WebPosto MCP Server",
    description="Servidor MCP para integração com a API da Quality Automação (WebPosto).",
    version="1.0.0"
)

# Incluir as rotas do MCP no FastAPI
app.include_router(mcp.router)

@app.get("/health", tags=["Status"])
async def health_check():
    """Verifica a saúde do servidor."""
    return {"status": "ok"}

# Ponto de entrada para uvicorn (para desenvolvimento)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
