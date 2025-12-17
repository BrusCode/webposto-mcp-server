#!/usr/bin/env python3

from typing import Optional
from mcp.server.fastmcp import tool
from src.api.webposto_client import api_client

@tool()
def consultar_estoque_produtos(
    empresa_codigo: Optional[str] = None,
    limite: Optional[int] = 100
) -> str:
    """
    Consulta o estoque atual de produtos.

    Args:
        empresa_codigo: Código da empresa (opcional).
        limite: Limite de registros (máximo 2000, padrão: 100).

    Returns:
        Um relatório formatado sobre o estoque dos produtos ou uma mensagem de erro.
    """
    params = {
        "limite": min(limite, 2000)
    }
    if empresa_codigo:
        params["empresaCodigo"] = empresa_codigo

    result = api_client.get("/ESTOQUE", params=params)

    if not result["success"]:
        return f'Erro ao consultar estoque: {result["error"]}'

    data = result.get("data", {})
    registros = data.get("resultados", []) if isinstance(data, dict) else data

    if not registros:
        return "Nenhum produto encontrado no estoque."

    output = ["Relatório de Estoque de Produtos\n"]
    for produto in registros:
        output.append(
            f'- Produto: {produto.get("produto", {}).get("nome")} | Estoque: {produto.get("estoqueAtual", 0):.2f} {produto.get("produto", {}).get("unidade")}'
        )
    
    return "\n".join(output)
