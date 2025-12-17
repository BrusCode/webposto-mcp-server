#!/usr/bin/env python3

from typing import Optional
from mcp.server.fastmcp import tool
from src.api.webposto_client import api_client

@tool()
def consultar_caixas(
    data_inicial: str,
    data_final: Optional[str] = None,
    turno: Optional[int] = None,
    empresa_codigo: Optional[str] = None,
    limite: Optional[int] = 100
) -> str:
    """
    Consulta informações de caixas no período especificado.

    Args:
        data_inicial: Data inicial no formato YYYY-MM-DD.
        data_final: Data final no formato YYYY-MM-DD (padrão: mesmo dia que data_inicial).
        turno: Número do turno (opcional).
        empresa_codigo: Código da empresa (opcional).
        limite: Limite de registros (máximo 2000, padrão: 100).

    Returns:
        Um relatório formatado sobre os caixas encontrados ou uma mensagem de erro.
    """
    if not data_final:
        data_final = data_inicial

    params = {
        "dataInicial": data_inicial,
        "dataFinal": data_final,
        "limite": min(limite, 2000)  # Garante que o limite não ultrapasse 2000
    }
    if turno:
        params["turno"] = turno
    if empresa_codigo:
        params["empresaCodigo"] = empresa_codigo

    result = api_client.get("/CAIXA", params=params)

    if not result["success"]:
        return f"Erro ao consultar caixas: {result["error"]}"

    data = result.get("data", {})
    registros = data.get("resultados", []) if isinstance(data, dict) else data

    if not registros:
        return f"Nenhum caixa encontrado para o período de {data_inicial} a {data_final}."

    # Formatação da saída
    output = [f"Relatório de Caixas ({data_inicial} a {data_final})\n"]
    for caixa in registros:
        status = "Fechado" if caixa.get("fechamento") else "Aberto"
        output.append(
            f"- Caixa ID: {caixa.get("caixaCodigo")} | Status: {status} | Operador: {caixa.get("operador", {}).get("nome")} | Total: R$ {caixa.get("apurado", 0):.2f}"
        )
    
    return "\n".join(output)
