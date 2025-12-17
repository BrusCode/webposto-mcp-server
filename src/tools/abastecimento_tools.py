#!/usr/bin/env python3

from typing import Optional
from mcp.server.fastmcp import tool
from src.api.webposto_client import api_client

@tool()
def consultar_abastecimentos(
    data_inicial: str,
    data_final: Optional[str] = None,
    bico_codigo: Optional[str] = None,
    funcionario_codigo: Optional[str] = None,
    limite: Optional[int] = 100
) -> str:
    """
    Consulta abastecimentos realizados no período.

    Args:
        data_inicial: Data inicial no formato YYYY-MM-DD.
        data_final: Data final no formato YYYY-MM-DD (padrão: mesmo dia que data_inicial).
        bico_codigo: Código do bico (opcional).
        funcionario_codigo: Código do funcionário/frentista (opcional).
        limite: Limite de registros (máximo 2000, padrão: 100).

    Returns:
        Um relatório formatado sobre os abastecimentos encontrados ou uma mensagem de erro.
    """
    if not data_final:
        data_final = data_inicial

    params = {
        "dataInicial": data_inicial,
        "dataFinal": data_final,
        "limite": min(limite, 2000)
    }
    if bico_codigo:
        params["bicoCodigo"] = bico_codigo
    if funcionario_codigo:
        params["funcionarioCodigo"] = funcionario_codigo

    result = api_client.get("/ABASTECIMENTO", params=params)

    if not result["success"]:
        return f"Erro ao consultar abastecimentos: {result["error"]}"

    data = result.get("data", {})
    registros = data.get("resultados", []) if isinstance(data, dict) else data

    if not registros:
        return f"Nenhum abastecimento encontrado para o período de {data_inicial} a {data_final}."

    output = [f"Relatório de Abastecimentos ({data_inicial} a {data_final})\n"]
    for abs in registros:
        output.append(
            f"- Abastecimento ID: {abs.get("abastecimentoCodigo")} | Bico: {abs.get("bico")} | Litros: {abs.get("litros", 0):.3f} | Total: R$ {abs.get("total", 0):.2f}"
        )
    
    return "\n".join(output)
