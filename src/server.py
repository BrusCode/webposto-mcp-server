#!/usr/bin/env python3
"""
WebPosto MCP Server - Quality Automação
Servidor MCP (Model Context Protocol) para integração com o sistema WebPosto.

Este servidor fornece ferramentas para assistentes de IA interagirem com a API
do WebPosto, permitindo consultas e operações no sistema de gestão de postos.

Autor: Quality Automação
Versão: 1.2.0

IMPORTANTE: A autenticação é feita via parâmetro "chave" na query string,
conforme documentação oficial da API WebPosto.
"""

import asyncio
import sys
import json
import logging
import os
import requests
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURAÇÃO DA API
# =============================================================================

WEBPOSTO_BASE_URL = os.getenv('WEBPOSTO_URL', 'https://web.qualityautomacao.com.br')
API_KEY = os.getenv('WEBPOSTO_API_KEY', '')
DEFAULT_EMPRESA_CODIGO = os.getenv('WEBPOSTO_EMPRESA_CODIGO', '')

def get_headers():
    """Retorna os headers para requisições à API."""
    return {
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }

# =============================================================================
# CLIENTE HTTP
# =============================================================================

class WebPostoClient:
    """Cliente HTTP para comunicação com a API WebPosto."""
    
    def __init__(self, base_url: str = WEBPOSTO_BASE_URL):
        self.base_url = base_url.rstrip('/')
        self.timeout = 30
    
    def _add_auth_param(self, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Adiciona o parâmetro de autenticação 'chave' aos parâmetros da requisição."""
        if params is None:
            params = {}
        if API_KEY:
            params['chave'] = API_KEY
        return params
    
    def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Executa uma requisição HTTP para a API."""
        url = f"{self.base_url}{endpoint}"
        params = self._add_auth_param(params)
        
        try:
            logger.info(f"Requisição {method} para: {url}")
            
            response = requests.request(
                method=method,
                url=url,
                headers=get_headers(),
                params=params,
                json=data,
                timeout=self.timeout
            )
            
            logger.info(f"Status: {response.status_code}")
            
            if response.status_code == 204:
                return {"success": True, "data": None, "message": "Operação realizada com sucesso"}
            
            if 200 <= response.status_code < 300:
                try:
                    return {"success": True, "data": response.json()}
                except json.JSONDecodeError:
                    return {"success": True, "data": response.text}
            else:
                error_msg = response.text[:500] if response.text else f"Erro HTTP {response.status_code}"
                return {"success": False, "error": f"Erro {response.status_code}: {error_msg}", "status_code": response.status_code}
                
        except requests.exceptions.Timeout:
            return {"success": False, "error": "Timeout na requisição (30s)"}
        except requests.exceptions.ConnectionError as e:
            return {"success": False, "error": f"Erro de conexão: {e}"}
        except requests.exceptions.RequestException as e:
            return {"success": False, "error": str(e)}
    
    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self._make_request("GET", endpoint, params=params)
    
    def post(self, endpoint: str, data: Dict[str, Any], params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self._make_request("POST", endpoint, params=params, data=data)
    
    def put(self, endpoint: str, data: Dict[str, Any], params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self._make_request("PUT", endpoint, params=params, data=data)
    
    def delete(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self._make_request("DELETE", endpoint, params=params)

client = WebPostoClient()

# =============================================================================
# SERVIDOR MCP
# =============================================================================

mcp = FastMCP("webposto-mcp")

# =============================================================================
# UTILITÁRIOS
# =============================================================================

def format_response(data: Any, max_records: int = 50) -> str:
    """Formata a resposta da API para exibição."""
    if isinstance(data, list):
        records = data
    elif isinstance(data, dict):
        records = data.get('resultados', data.get('registros', data.get('data', [])))
        if not isinstance(records, list):
            return json.dumps(data, indent=2, ensure_ascii=False)
    else:
        return str(data)
    
    if not records:
        return "Nenhum registro encontrado."
    
    output = [f"Total de registros: {len(records)}\n"]
    for i, record in enumerate(records[:max_records], 1):
        record_str = json.dumps(record, indent=2, ensure_ascii=False)
        if len(record_str) > 1000:
            record_str = record_str[:1000] + "..."
        output.append(f"--- Registro {i} ---\n{record_str}")
    
    if len(records) > max_records:
        output.append(f"\n... e mais {len(records) - max_records} registros")
    
    return "\n".join(output)


# =============================================================================
# FERRAMENTAS - INTEGRAÇÕES
# =============================================================================


@mcp.tool()
def receber_titulo_convertido(dados: Dict[str, Any]) -> str:
    """receberTituloConvertido - PUT /INTEGRACAO/RECEBER_TITULO_CONVERTIDO"""
    endpoint = f"/INTEGRACAO/RECEBER_TITULO_CONVERTIDO"
    params = {}

    result = client.put(endpoint, data=dados, params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return f"Operação realizada com sucesso.\n{format_response(result.get('data', {}))}"


@mcp.tool()
def receber_titulo(dados: Dict[str, Any]) -> str:
    """receberTitulo - PUT /INTEGRACAO/RECEBER_TITULO"""
    endpoint = f"/INTEGRACAO/RECEBER_TITULO"
    params = {}

    result = client.put(endpoint, data=dados, params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return f"Operação realizada com sucesso.\n{format_response(result.get('data', {}))}"


@mcp.tool()
def receber_cheque(dados: Dict[str, Any], empresa_codigo: Optional[int] = None) -> str:
    """receberCheque - PUT /INTEGRACAO/RECEBER_CHEQUE"""
    endpoint = f"/INTEGRACAO/RECEBER_CHEQUE"
    params = {}
    if empresa_codigo is not None:
        params["empresaCodigo"] = empresa_codigo
    result = client.put(endpoint, data=dados, params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return f"Operação realizada com sucesso.\n{format_response(result.get('data', {}))}"


@mcp.tool()
def receber_cartoes(dados: Dict[str, Any]) -> str:
    """receberCartoes - PUT /INTEGRACAO/RECEBER_CARTAO"""
    endpoint = f"/INTEGRACAO/RECEBER_CARTAO"
    params = {}

    result = client.put(endpoint, data=dados, params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return f"Operação realizada com sucesso.\n{format_response(result.get('data', {}))}"


@mcp.tool()
def reajustar_estoque_produto_combustivel(dados: Dict[str, Any]) -> str:
    """reajustarEstoqueProdutoCombustivel - PUT /INTEGRACAO/REAJUSTAR_ESTOQUE_PRODUTO_COMBUSTIVEL"""
    endpoint = f"/INTEGRACAO/REAJUSTAR_ESTOQUE_PRODUTO_COMBUSTIVEL"
    params = {}

    result = client.put(endpoint, data=dados, params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return f"Operação realizada com sucesso.\n{format_response(result.get('data', {}))}"


@mcp.tool()
def alterar_cliente_grupo(id: str, dados: Dict[str, Any]) -> str:
    """alterarClienteGrupo - PUT /INTEGRACAO/GRUPO_CLIENTE/{id}"""
    endpoint = f"/INTEGRACAO/GRUPO_CLIENTE/{id}"
    params = {}

    result = client.put(endpoint, data=dados, params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return f"Operação realizada com sucesso.\n{format_response(result.get('data', {}))}"


@mcp.tool()
def alterar_cliente(id: str, dados: Dict[str, Any]) -> str:
    """alterarCliente - PUT /INTEGRACAO/CLIENTE/{id}"""
    endpoint = f"/INTEGRACAO/CLIENTE/{id}"
    params = {}

    result = client.put(endpoint, data=dados, params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return f"Operação realizada com sucesso.\n{format_response(result.get('data', {}))}"


@mcp.tool()
def alterar_produto(id: str, dados: Dict[str, Any], empresa_codigo: Optional[int] = None) -> str:
    """alterarProduto - PUT /INTEGRACAO/ALTERAR_PRODUTO/{id}"""
    endpoint = f"/INTEGRACAO/ALTERAR_PRODUTO/{id}"
    params = {}
    if empresa_codigo is not None:
        params["empresaCodigo"] = empresa_codigo
    result = client.put(endpoint, data=dados, params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return f"Operação realizada com sucesso.\n{format_response(result.get('data', {}))}"


@mcp.tool()
def consultar_transferencia_bancaria(data_inicial: str, data_final: str, empresa_codigo: Optional[int] = None, venda_codigo: Optional[int] = None, tipo_inclusao: Optional[int] = None, conta_codigo: Optional[int] = None, ultimo_codigo: Optional[int] = None, limite: Optional[int] = None) -> str:
    """consultarTransferenciaBancaria - GET /INTEGRACAO/TRANSFERENCIA_BANCARIA"""
    params = {}
    if empresa_codigo is not None:
        params["empresaCodigo"] = empresa_codigo
    if data_inicial is not None:
        params["dataInicial"] = data_inicial
    if data_final is not None:
        params["dataFinal"] = data_final
    if venda_codigo is not None:
        params["vendaCodigo"] = venda_codigo
    if tipo_inclusao is not None:
        params["tipoInclusao"] = tipo_inclusao
    if conta_codigo is not None:
        params["contaCodigo"] = conta_codigo
    if ultimo_codigo is not None:
        params["ultimoCodigo"] = ultimo_codigo
    if limite is not None:
        params["limite"] = limite
    result = client.get("/INTEGRACAO/TRANSFERENCIA_BANCARIA", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def incluir_transferencia(dados: Dict[str, Any]) -> str:
    """incluirTransferencia - POST /INTEGRACAO/TRANSFERENCIA_BANCARIA"""
    params = {}

    result = client.post("/INTEGRACAO/TRANSFERENCIA_BANCARIA", data=dados, params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return f"Operação realizada com sucesso.\n{format_response(result.get('data', {}))}"


@mcp.tool()
def consultar_titulo_receber(data_inicial: str, data_final: str, turno: Optional[int] = None, empresa_codigo: Optional[int] = None, data_hora_atualizacao: Optional[str] = None, apenas_pendente: Optional[bool] = None, codigo_duplicata: Optional[int] = None, data_filtro: Optional[str] = None, ultimo_codigo: Optional[int] = None, limite: Optional[int] = None, convertido: Optional[bool] = None, venda_codigo: Optional[list] = None) -> str:
    """consultarTituloReceber - GET /INTEGRACAO/TITULO_RECEBER"""
    params = {}
    if turno is not None:
        params["turno"] = turno
    if empresa_codigo is not None:
        params["empresaCodigo"] = empresa_codigo
    if data_inicial is not None:
        params["dataInicial"] = data_inicial
    if data_final is not None:
        params["dataFinal"] = data_final
    if data_hora_atualizacao is not None:
        params["dataHoraAtualizacao"] = data_hora_atualizacao
    if apenas_pendente is not None:
        params["apenasPendente"] = apenas_pendente
    if codigo_duplicata is not None:
        params["codigoDuplicata"] = codigo_duplicata
    if data_filtro is not None:
        params["dataFiltro"] = data_filtro
    if ultimo_codigo is not None:
        params["ultimoCodigo"] = ultimo_codigo
    if limite is not None:
        params["limite"] = limite
    if convertido is not None:
        params["convertido"] = convertido
    if venda_codigo is not None:
        params["vendaCodigo"] = venda_codigo
    result = client.get("/INTEGRACAO/TITULO_RECEBER", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def incluir_titulo_receber(dados: Dict[str, Any]) -> str:
    """incluirTituloReceber - POST /INTEGRACAO/TITULO_RECEBER"""
    params = {}

    result = client.post("/INTEGRACAO/TITULO_RECEBER", data=dados, params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return f"Operação realizada com sucesso.\n{format_response(result.get('data', {}))}"


@mcp.tool()
def consultar_titulo_pagar(data_inicial: Optional[str] = None, data_final: Optional[str] = None, data_hora_atualizacao: Optional[str] = None, apenas_pendente: Optional[bool] = None, data_filtro: Optional[str] = None, ultimo_codigo: Optional[int] = None, limite: Optional[int] = None, empresa_codigo: Optional[int] = None, nota_entrada_codigo: Optional[int] = None, titulo_pagar_codigo: Optional[int] = None, fornecedor_codigo: Optional[int] = None, linha_digitavel: Optional[str] = None, autorizado: Optional[bool] = None, tipo_lancamento: Optional[str] = None) -> str:
    """consultarTituloPagar - GET /INTEGRACAO/TITULO_PAGAR"""
    params = {}
    if data_inicial is not None:
        params["dataInicial"] = data_inicial
    if data_final is not None:
        params["dataFinal"] = data_final
    if data_hora_atualizacao is not None:
        params["dataHoraAtualizacao"] = data_hora_atualizacao
    if apenas_pendente is not None:
        params["apenasPendente"] = apenas_pendente
    if data_filtro is not None:
        params["dataFiltro"] = data_filtro
    if ultimo_codigo is not None:
        params["ultimoCodigo"] = ultimo_codigo
    if limite is not None:
        params["limite"] = limite
    if empresa_codigo is not None:
        params["empresaCodigo"] = empresa_codigo
    if nota_entrada_codigo is not None:
        params["notaEntradaCodigo"] = nota_entrada_codigo
    if titulo_pagar_codigo is not None:
        params["tituloPagarCodigo"] = titulo_pagar_codigo
    if fornecedor_codigo is not None:
        params["fornecedorCodigo"] = fornecedor_codigo
    if linha_digitavel is not None:
        params["linhaDigitavel"] = linha_digitavel
    if autorizado is not None:
        params["autorizado"] = autorizado
    if tipo_lancamento is not None:
        params["tipoLancamento"] = tipo_lancamento
    result = client.get("/INTEGRACAO/TITULO_PAGAR", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def incluir_titulo_pagar(dados: Dict[str, Any]) -> str:
    """incluirTituloPagar - POST /INTEGRACAO/TITULO_PAGAR"""
    params = {}

    result = client.post("/INTEGRACAO/TITULO_PAGAR", data=dados, params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return f"Operação realizada com sucesso.\n{format_response(result.get('data', {}))}"


@mcp.tool()
def consultar_revendedores() -> str:
    """consultarRevendedores - POST /INTEGRACAO/REVENDEDORES_ANP"""
    params = {}

    result = client.post("/INTEGRACAO/REVENDEDORES_ANP", data=dados, params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return f"Operação realizada com sucesso.\n{format_response(result.get('data', {}))}"


@mcp.tool()
def reajustar_produto(dados: Dict[str, Any]) -> str:
    """reajustarProduto - POST /INTEGRACAO/REAJUSTAR_PRODUTO"""
    params = {}

    result = client.post("/INTEGRACAO/REAJUSTAR_PRODUTO", data=dados, params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return f"Operação realizada com sucesso.\n{format_response(result.get('data', {}))}"


@mcp.tool()
def produto_inventario(dados: Dict[str, Any]) -> str:
    """produtoInventario - POST /INTEGRACAO/PRODUTO_INVENTARIO"""
    params = {}

    result = client.post("/INTEGRACAO/PRODUTO_INVENTARIO", data=dados, params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return f"Operação realizada com sucesso.\n{format_response(result.get('data', {}))}"


@mcp.tool()
def incluir_produto_comissao(dados: Dict[str, Any]) -> str:
    """incluirProdutoComissao - POST /INTEGRACAO/PRODUTO_COMISSAO"""
    params = {}

    result = client.post("/INTEGRACAO/PRODUTO_COMISSAO", data=dados, params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return f"Operação realizada com sucesso.\n{format_response(result.get('data', {}))}"


@mcp.tool()
def incluir_prazo_tabela_preco_item(id: str, dados: Dict[str, Any]) -> str:
    """incluirPrazoTabelaPrecoItem - POST /INTEGRACAO/PRAZO_TABELA_PRECO/{id}/ITEM"""
    params = {}

    result = client.post("/INTEGRACAO/PRAZO_TABELA_PRECO/{id}/ITEM", data=dados, params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return f"Operação realizada com sucesso.\n{format_response(result.get('data', {}))}"


@mcp.tool()
def pedido_compra(dados: Dict[str, Any]) -> str:
    """pedidoCompra - POST /INTEGRACAO/PEDIDO_COMPRAS"""
    params = {}

    result = client.post("/INTEGRACAO/PEDIDO_COMPRAS", data=dados, params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return f"Operação realizada com sucesso.\n{format_response(result.get('data', {}))}"


@mcp.tool()
def consultar_cliente(cliente_codigo_externo: Optional[str] = None, cliente_codigo: Optional[list] = None, empresa_codigo: Optional[int] = None, retorna_observacoes: Optional[bool] = None, data_hora_atualizacao: Optional[str] = None, frota: Optional[bool] = None, faturamento: Optional[bool] = None, limites_bloqueios: Optional[bool] = None, ultimo_codigo: Optional[int] = None, limite: Optional[int] = None) -> str:
    """consultarCliente - GET /INTEGRACAO/CLIENTE"""
    params = {}
    if cliente_codigo_externo is not None:
        params["clienteCodigoExterno"] = cliente_codigo_externo
    if cliente_codigo is not None:
        params["clienteCodigo"] = cliente_codigo
    if empresa_codigo is not None:
        params["empresaCodigo"] = empresa_codigo
    if retorna_observacoes is not None:
        params["retornaObservacoes"] = retorna_observacoes
    if data_hora_atualizacao is not None:
        params["dataHoraAtualizacao"] = data_hora_atualizacao
    if frota is not None:
        params["frota"] = frota
    if faturamento is not None:
        params["faturamento"] = faturamento
    if limites_bloqueios is not None:
        params["limitesBloqueios"] = limites_bloqueios
    if ultimo_codigo is not None:
        params["ultimoCodigo"] = ultimo_codigo
    if limite is not None:
        params["limite"] = limite
    result = client.get("/INTEGRACAO/CLIENTE", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def incluir_cliente(dados: Dict[str, Any]) -> str:
    """incluirCliente - POST /INTEGRACAO/CLIENTE"""
    params = {}

    result = client.post("/INTEGRACAO/CLIENTE", data=dados, params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return f"Operação realizada com sucesso.\n{format_response(result.get('data', {}))}"


@mcp.tool()
def incluir_cliente_1(dados: Dict[str, Any]) -> str:
    """incluirCliente_1 - POST /INTEGRACAO/PEDIDO_COMBUSTIVEL/CLIENTE"""
    params = {}

    result = client.post("/INTEGRACAO/PEDIDO_COMBUSTIVEL/CLIENTE", data=dados, params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return f"Operação realizada com sucesso.\n{format_response(result.get('data', {}))}"


@mcp.tool()
def consultar_movimento_conta(empresa_codigo: Optional[int] = None, data_inicial: Optional[str] = None, data_final: Optional[str] = None, ultimo_codigo: Optional[int] = None, limite: Optional[int] = None, mostra_saldo: Optional[bool] = None, data_hora_atualizacao: Optional[str] = None, documento_origem_codigo: Optional[int] = None, tipo_documento_origem: Optional[str] = None) -> str:
    """consultarMovimentoConta - GET /INTEGRACAO/MOVIMENTO_CONTA"""
    params = {}
    if empresa_codigo is not None:
        params["empresaCodigo"] = empresa_codigo
    if data_inicial is not None:
        params["dataInicial"] = data_inicial
    if data_final is not None:
        params["dataFinal"] = data_final
    if ultimo_codigo is not None:
        params["ultimoCodigo"] = ultimo_codigo
    if limite is not None:
        params["limite"] = limite
    if mostra_saldo is not None:
        params["mostraSaldo"] = mostra_saldo
    if data_hora_atualizacao is not None:
        params["dataHoraAtualizacao"] = data_hora_atualizacao
    if documento_origem_codigo is not None:
        params["documentoOrigemCodigo"] = documento_origem_codigo
    if tipo_documento_origem is not None:
        params["tipoDocumentoOrigem"] = tipo_documento_origem
    result = client.get("/INTEGRACAO/MOVIMENTO_CONTA", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def incluir_movimento_conta(dados: Dict[str, Any]) -> str:
    """incluirMovimentoConta - POST /INTEGRACAO/MOVIMENTO_CONTA"""
    params = {}

    result = client.post("/INTEGRACAO/MOVIMENTO_CONTA", data=dados, params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return f"Operação realizada com sucesso.\n{format_response(result.get('data', {}))}"


@mcp.tool()
def consultar_lancamento_contabil(data_inicial: str, data_final: str, empresa_codigo: Optional[int] = None, ultimo_codigo: Optional[int] = None, limite: Optional[int] = None, lote_contabil: Optional[int] = None) -> str:
    """consultarLancamentoContabil - GET /INTEGRACAO/LANCAMENTO_CONTABIL"""
    params = {}
    if empresa_codigo is not None:
        params["empresaCodigo"] = empresa_codigo
    if data_inicial is not None:
        params["dataInicial"] = data_inicial
    if data_final is not None:
        params["dataFinal"] = data_final
    if ultimo_codigo is not None:
        params["ultimoCodigo"] = ultimo_codigo
    if limite is not None:
        params["limite"] = limite
    if lote_contabil is not None:
        params["loteContabil"] = lote_contabil
    result = client.get("/INTEGRACAO/LANCAMENTO_CONTABIL", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def incluir_lancamento_contabil(dados: Dict[str, Any]) -> str:
    """incluirLancamentoContabil - POST /INTEGRACAO/LANCAMENTO_CONTABIL"""
    params = {}

    result = client.post("/INTEGRACAO/LANCAMENTO_CONTABIL", data=dados, params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return f"Operação realizada com sucesso.\n{format_response(result.get('data', {}))}"


@mcp.tool()
def incluir_produto(dados: Dict[str, Any], empresa_codigo: Optional[int] = None) -> str:
    """incluirProduto - POST /INTEGRACAO/INCLUIR_PRODUTO"""
    params = {}
    if empresa_codigo is not None:
        params["empresaCodigo"] = empresa_codigo
    result = client.post("/INTEGRACAO/INCLUIR_PRODUTO", data=dados, params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return f"Operação realizada com sucesso.\n{format_response(result.get('data', {}))}"


@mcp.tool()
def incluir_ofx(dados: Dict[str, Any]) -> str:
    """incluirOfx - POST /INTEGRACAO/INCLUIR_OFX"""
    params = {}

    result = client.post("/INTEGRACAO/INCLUIR_OFX", data=dados, params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return f"Operação realizada com sucesso.\n{format_response(result.get('data', {}))}"


@mcp.tool()
def consultar_grupo_cliente(grupo_codigo: Optional[int] = None, grupo_codigo_externo: Optional[str] = None, ultimo_codigo: Optional[int] = None, limite: Optional[int] = None) -> str:
    """consultarGrupoCliente - GET /INTEGRACAO/GRUPO_CLIENTE"""
    params = {}
    if grupo_codigo is not None:
        params["grupoCodigo"] = grupo_codigo
    if grupo_codigo_externo is not None:
        params["grupoCodigoExterno"] = grupo_codigo_externo
    if ultimo_codigo is not None:
        params["ultimoCodigo"] = ultimo_codigo
    if limite is not None:
        params["limite"] = limite
    result = client.get("/INTEGRACAO/GRUPO_CLIENTE", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def incluir_cliente_grupo(dados: Dict[str, Any]) -> str:
    """incluirClienteGrupo - POST /INTEGRACAO/GRUPO_CLIENTE"""
    params = {}

    result = client.post("/INTEGRACAO/GRUPO_CLIENTE", data=dados, params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return f"Operação realizada com sucesso.\n{format_response(result.get('data', {}))}"


@mcp.tool()
def envio_whata_app() -> str:
    """envioWhataApp - POST /INTEGRACAO/ENVIO_WHATSAPP"""
    params = {}

    result = client.post("/INTEGRACAO/ENVIO_WHATSAPP", data=dados, params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return f"Operação realizada com sucesso.\n{format_response(result.get('data', {}))}"


@mcp.tool()
def envio_email() -> str:
    """envioEmail - POST /INTEGRACAO/ENVIO_EMAIL"""
    params = {}

    result = client.post("/INTEGRACAO/ENVIO_EMAIL", data=dados, params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return f"Operação realizada com sucesso.\n{format_response(result.get('data', {}))}"


@mcp.tool()
def vincular_cliente_unidade_negocio(dados: Dict[str, Any]) -> str:
    """vincularClienteUnidadeNegocio - POST /INTEGRACAO/CLIENTE_UNIDADE_NEGOCIO"""
    params = {}

    result = client.post("/INTEGRACAO/CLIENTE_UNIDADE_NEGOCIO", data=dados, params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return f"Operação realizada com sucesso.\n{format_response(result.get('data', {}))}"


@mcp.tool()
def incluir_cliente_prazo(codigo_cliente: str, dados: Dict[str, Any]) -> str:
    """incluirClientePrazo - POST /INTEGRACAO/CLIENTE_PRAZO/{codigoCliente}"""
    params = {}

    result = client.post("/INTEGRACAO/CLIENTE_PRAZO/{codigoCliente}", data=dados, params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return f"Operação realizada com sucesso.\n{format_response(result.get('data', {}))}"


@mcp.tool()
def consultar_cartao(data_inicial: str, data_final: str, turno: Optional[int] = None, empresa_codigo: Optional[int] = None, apenas_pendente: Optional[bool] = None, data_filtro: Optional[str] = None, data_hora_atualizacao: Optional[str] = None, ultimo_codigo: Optional[int] = None, limite: Optional[int] = None, venda_codigo: Optional[list] = None) -> str:
    """consultarCartao - GET /INTEGRACAO/CARTAO"""
    params = {}
    if turno is not None:
        params["turno"] = turno
    if empresa_codigo is not None:
        params["empresaCodigo"] = empresa_codigo
    if data_inicial is not None:
        params["dataInicial"] = data_inicial
    if data_final is not None:
        params["dataFinal"] = data_final
    if apenas_pendente is not None:
        params["apenasPendente"] = apenas_pendente
    if data_filtro is not None:
        params["dataFiltro"] = data_filtro
    if data_hora_atualizacao is not None:
        params["dataHoraAtualizacao"] = data_hora_atualizacao
    if ultimo_codigo is not None:
        params["ultimoCodigo"] = ultimo_codigo
    if limite is not None:
        params["limite"] = limite
    if venda_codigo is not None:
        params["vendaCodigo"] = venda_codigo
    result = client.get("/INTEGRACAO/CARTAO", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def incluir_cartao(dados: Dict[str, Any]) -> str:
    """incluirCartao - POST /INTEGRACAO/CARTAO"""
    params = {}

    result = client.post("/INTEGRACAO/CARTAO", data=dados, params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return f"Operação realizada com sucesso.\n{format_response(result.get('data', {}))}"


@mcp.tool()
def incluir_brinde(dados: Dict[str, Any]) -> str:
    """incluirBrinde - POST /INTEGRACAO/BRINDE"""
    params = {}

    result = client.post("/INTEGRACAO/BRINDE", data=dados, params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return f"Operação realizada com sucesso.\n{format_response(result.get('data', {}))}"


@mcp.tool()
def autoriza_pagamento_abastecimento(dados: Dict[str, Any]) -> str:
    """autorizaPagamentoAbastecimento - POST /INTEGRACAO/AUTORIZA_PAGAMENTO_ABASTECIMENTO"""
    params = {}

    result = client.post("/INTEGRACAO/AUTORIZA_PAGAMENTO_ABASTECIMENTO", data=dados, params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return f"Operação realizada com sucesso.\n{format_response(result.get('data', {}))}"


@mcp.tool()
def autorizar_nfe(nota_codigo: str) -> str:
    """autorizarNfe - POST /INTEGRACAO/AUTORIZAR_NFE_SAIDA/{notaCodigo}"""
    params = {}

    result = client.post("/INTEGRACAO/AUTORIZAR_NFE_SAIDA/{notaCodigo}", data=dados, params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return f"Operação realizada com sucesso.\n{format_response(result.get('data', {}))}"


@mcp.tool()
def alterar_preco_combustivel() -> str:
    """alterarPrecoCombustivel - POST /INTEGRACAO/ALTERACAO_PRECO_COMBUSTIVEL"""
    params = {}

    result = client.post("/INTEGRACAO/ALTERACAO_PRECO_COMBUSTIVEL", data=dados, params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return f"Operação realizada com sucesso.\n{format_response(result.get('data', {}))}"


@mcp.tool()
def pagar_titulo_pagar(dados: Dict[str, Any]) -> str:
    """pagarTituloPagar - PATCH /INTEGRACAO/TITULO_PAGAR/PAGAR"""
    endpoint = f"/INTEGRACAO/TITULO_PAGAR/PAGAR"
    params = {}

    result = client.put(endpoint, data=dados, params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return f"Operação realizada com sucesso.\n{format_response(result.get('data', {}))}"


@mcp.tool()
def excluir_cartao(id: str) -> str:
    """excluirCartao - DELETE /INTEGRACAO/CARTAO/{id}"""
    endpoint = f"/INTEGRACAO/CARTAO/{id}"
    params = {}

    result = client.delete(endpoint, params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return "Registro excluído com sucesso."


@mcp.tool()
def alterar_cartao(id: str, dados: Dict[str, Any]) -> str:
    """alterarCartao - PATCH /INTEGRACAO/CARTAO/{id}"""
    endpoint = f"/INTEGRACAO/CARTAO/{id}"
    params = {}

    result = client.put(endpoint, data=dados, params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return f"Operação realizada com sucesso.\n{format_response(result.get('data', {}))}"


@mcp.tool()
def venda_resumo(empresa_codigo: Optional[list] = None, data_inicial: Optional[str] = None, data_final: Optional[str] = None, situacao: Optional[str] = None) -> str:
    """vendaResumo - GET /INTEGRACAO/VENDA_RESUMO"""
    params = {}
    if empresa_codigo is not None:
        params["empresaCodigo"] = empresa_codigo
    if data_inicial is not None:
        params["dataInicial"] = data_inicial
    if data_final is not None:
        params["dataFinal"] = data_final
    if situacao is not None:
        params["situacao"] = situacao
    result = client.get("/INTEGRACAO/VENDA_RESUMO", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_item_fidelidade(venda_item_voucher_codigo: Optional[int] = None, venda_item_codigo: Optional[list] = None, tipo_integracao_voucher: Optional[str] = None, ultimo_codigo: Optional[int] = None, limite: Optional[int] = None) -> str:
    """consultarItemFidelidade - GET /INTEGRACAO/VENDA_ITEM_FIDELIDADE"""
    params = {}
    if venda_item_voucher_codigo is not None:
        params["vendaItemVoucherCodigo"] = venda_item_voucher_codigo
    if venda_item_codigo is not None:
        params["vendaItemCodigo"] = venda_item_codigo
    if tipo_integracao_voucher is not None:
        params["tipoIntegracaoVoucher"] = tipo_integracao_voucher
    if ultimo_codigo is not None:
        params["ultimoCodigo"] = ultimo_codigo
    if limite is not None:
        params["limite"] = limite
    result = client.get("/INTEGRACAO/VENDA_ITEM_FIDELIDADE", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_venda_item(empresa_codigo: Optional[int] = None, usa_produto_lmc: Optional[bool] = None, data_inicial: Optional[str] = None, data_final: Optional[str] = None, tipo_data: Optional[str] = None, ultimo_codigo: Optional[int] = None, limite: Optional[int] = None, venda_codigo: Optional[list] = None) -> str:
    """consultarVendaItem - GET /INTEGRACAO/VENDA_ITEM"""
    params = {}
    if empresa_codigo is not None:
        params["empresaCodigo"] = empresa_codigo
    if usa_produto_lmc is not None:
        params["usaProdutoLmc"] = usa_produto_lmc
    if data_inicial is not None:
        params["dataInicial"] = data_inicial
    if data_final is not None:
        params["dataFinal"] = data_final
    if tipo_data is not None:
        params["tipoData"] = tipo_data
    if ultimo_codigo is not None:
        params["ultimoCodigo"] = ultimo_codigo
    if limite is not None:
        params["limite"] = limite
    if venda_codigo is not None:
        params["vendaCodigo"] = venda_codigo
    result = client.get("/INTEGRACAO/VENDA_ITEM", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_venda_forma_pagamento(turno: Optional[int] = None, empresa_codigo: Optional[int] = None, data_inicial: Optional[str] = None, data_final: Optional[str] = None, modelo_documento: Optional[str] = None, tipo_data: Optional[str] = None, ultimo_codigo: Optional[int] = None, limite: Optional[int] = None, venda_codigo: Optional[list] = None, situacao: Optional[str] = None, vendas_com_dfe: Optional[bool] = None) -> str:
    """consultarVendaFormaPagamento - GET /INTEGRACAO/VENDA_FORMA_PAGAMENTO"""
    params = {}
    if turno is not None:
        params["turno"] = turno
    if empresa_codigo is not None:
        params["empresaCodigo"] = empresa_codigo
    if data_inicial is not None:
        params["dataInicial"] = data_inicial
    if data_final is not None:
        params["dataFinal"] = data_final
    if modelo_documento is not None:
        params["modeloDocumento"] = modelo_documento
    if tipo_data is not None:
        params["tipoData"] = tipo_data
    if ultimo_codigo is not None:
        params["ultimoCodigo"] = ultimo_codigo
    if limite is not None:
        params["limite"] = limite
    if venda_codigo is not None:
        params["vendaCodigo"] = venda_codigo
    if situacao is not None:
        params["situacao"] = situacao
    if vendas_com_dfe is not None:
        params["vendasComDfe"] = vendas_com_dfe
    result = client.get("/INTEGRACAO/VENDA_FORMA_PAGAMENTO", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_venda(turno: Optional[int] = None, empresa_codigo: Optional[int] = None, data_inicial: Optional[str] = None, data_final: Optional[str] = None, modelo_documento: Optional[str] = None, tipo_data: Optional[str] = None, ultimo_codigo: Optional[int] = None, limite: Optional[int] = None, venda_codigo: Optional[list] = None, situacao: Optional[str] = None, vendas_com_dfe: Optional[bool] = None) -> str:
    """consultarVenda - GET /INTEGRACAO/VENDA"""
    params = {}
    if turno is not None:
        params["turno"] = turno
    if empresa_codigo is not None:
        params["empresaCodigo"] = empresa_codigo
    if data_inicial is not None:
        params["dataInicial"] = data_inicial
    if data_final is not None:
        params["dataFinal"] = data_final
    if modelo_documento is not None:
        params["modeloDocumento"] = modelo_documento
    if tipo_data is not None:
        params["tipoData"] = tipo_data
    if ultimo_codigo is not None:
        params["ultimoCodigo"] = ultimo_codigo
    if limite is not None:
        params["limite"] = limite
    if venda_codigo is not None:
        params["vendaCodigo"] = venda_codigo
    if situacao is not None:
        params["situacao"] = situacao
    if vendas_com_dfe is not None:
        params["vendasComDfe"] = vendas_com_dfe
    result = client.get("/INTEGRACAO/VENDA", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_venda_completa(id_list: str, vendas_com_dfe: Optional[bool] = None) -> str:
    """consultarVendaCompleta - GET /INTEGRACAO/VENDA/{idList}"""
    params = {}
    if vendas_com_dfe is not None:
        params["vendasComDfe"] = vendas_com_dfe
    result = client.get("/INTEGRACAO/VENDA/{idList}", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_vale_funcionario(data_inicial: str, data_final: str, empresa_codigo: Optional[list] = None, venda_codigo: Optional[int] = None, ultimo_codigo: Optional[int] = None, limite: Optional[int] = None, quitado: Optional[bool] = None, data_hora_atualizacao: Optional[str] = None, origem: Optional[str] = None) -> str:
    """consultarValeFuncionario - GET /INTEGRACAO/VALE_FUNCIONARIO"""
    params = {}
    if empresa_codigo is not None:
        params["empresaCodigo"] = empresa_codigo
    if data_inicial is not None:
        params["dataInicial"] = data_inicial
    if data_final is not None:
        params["dataFinal"] = data_final
    if venda_codigo is not None:
        params["vendaCodigo"] = venda_codigo
    if ultimo_codigo is not None:
        params["ultimoCodigo"] = ultimo_codigo
    if limite is not None:
        params["limite"] = limite
    if quitado is not None:
        params["quitado"] = quitado
    if data_hora_atualizacao is not None:
        params["dataHoraAtualizacao"] = data_hora_atualizacao
    if origem is not None:
        params["origem"] = origem
    result = client.get("/INTEGRACAO/VALE_FUNCIONARIO", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_usuario_empresa(ultimo_codigo: Optional[int] = None, limite: Optional[int] = None) -> str:
    """consultarUsuarioEmpresa - GET /INTEGRACAO/USUARIO_EMPRESA"""
    params = {}
    if ultimo_codigo is not None:
        params["ultimoCodigo"] = ultimo_codigo
    if limite is not None:
        params["limite"] = limite
    result = client.get("/INTEGRACAO/USUARIO_EMPRESA", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_usuario(ultimo_codigo: Optional[int] = None, limite: Optional[int] = None) -> str:
    """consultarUsuario - GET /INTEGRACAO/USUARIO"""
    params = {}
    if ultimo_codigo is not None:
        params["ultimoCodigo"] = ultimo_codigo
    if limite is not None:
        params["limite"] = limite
    result = client.get("/INTEGRACAO/USUARIO", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def troca_preco(data_inicial: str, data_final: str, realizada: Optional[bool] = None, tipo_produto: Optional[str] = None, empresa_codigo: Optional[int] = None, ultimo_codigo: Optional[int] = None, limite: Optional[int] = None) -> str:
    """trocaPreco - GET /INTEGRACAO/TROCA_PRECO"""
    params = {}
    if data_inicial is not None:
        params["dataInicial"] = data_inicial
    if data_final is not None:
        params["dataFinal"] = data_final
    if realizada is not None:
        params["realizada"] = realizada
    if tipo_produto is not None:
        params["tipoProduto"] = tipo_produto
    if empresa_codigo is not None:
        params["empresaCodigo"] = empresa_codigo
    if ultimo_codigo is not None:
        params["ultimoCodigo"] = ultimo_codigo
    if limite is not None:
        params["limite"] = limite
    result = client.get("/INTEGRACAO/TROCA_PRECO", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_tanque(tanque_codigo: Optional[int] = None, empresa_codigo: Optional[int] = None, ultimo_codigo: Optional[int] = None, limite: Optional[int] = None) -> str:
    """consultarTanque - GET /INTEGRACAO/TANQUE"""
    params = {}
    if tanque_codigo is not None:
        params["tanqueCodigo"] = tanque_codigo
    if empresa_codigo is not None:
        params["empresaCodigo"] = empresa_codigo
    if ultimo_codigo is not None:
        params["ultimoCodigo"] = ultimo_codigo
    if limite is not None:
        params["limite"] = limite
    result = client.get("/INTEGRACAO/TANQUE", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def tabela_preco_prazo(tabela_preco_prazo_codigo: Optional[int] = None, ultimo_codigo: Optional[int] = None, limite: Optional[int] = None) -> str:
    """tabelaPrecoPrazo - GET /INTEGRACAO/TABELA_PRECO_PRAZO"""
    params = {}
    if tabela_preco_prazo_codigo is not None:
        params["tabelaPrecoPrazoCodigo"] = tabela_preco_prazo_codigo
    if ultimo_codigo is not None:
        params["ultimoCodigo"] = ultimo_codigo
    if limite is not None:
        params["limite"] = limite
    result = client.get("/INTEGRACAO/TABELA_PRECO_PRAZO", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_sat(data_inicial: str, data_final: str, empresa_codigo: Optional[list] = None, venda_codigo: Optional[int] = None, ultimo_codigo: Optional[int] = None, limite: Optional[int] = None, quitado: Optional[bool] = None, data_hora_atualizacao: Optional[str] = None, origem: Optional[str] = None) -> str:
    """consultarSat - GET /INTEGRACAO/SAT"""
    params = {}
    if empresa_codigo is not None:
        params["empresaCodigo"] = empresa_codigo
    if data_inicial is not None:
        params["dataInicial"] = data_inicial
    if data_final is not None:
        params["dataFinal"] = data_final
    if venda_codigo is not None:
        params["vendaCodigo"] = venda_codigo
    if ultimo_codigo is not None:
        params["ultimoCodigo"] = ultimo_codigo
    if limite is not None:
        params["limite"] = limite
    if quitado is not None:
        params["quitado"] = quitado
    if data_hora_atualizacao is not None:
        params["dataHoraAtualizacao"] = data_hora_atualizacao
    if origem is not None:
        params["origem"] = origem
    result = client.get("/INTEGRACAO/SAT", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def sangria_caixa(data_inicial: Optional[str] = None, data_final: Optional[str] = None, data_hora_atualizacao: Optional[str] = None, empresa_codigo: Optional[int] = None, caixa_codigo: Optional[int] = None, funcionario_codigo: Optional[int] = None, ultimo_codigo: Optional[int] = None, limite: Optional[int] = None) -> str:
    """sangriaCaixa - GET /INTEGRACAO/SANGRIA_CAIXA"""
    params = {}
    if data_inicial is not None:
        params["dataInicial"] = data_inicial
    if data_final is not None:
        params["dataFinal"] = data_final
    if data_hora_atualizacao is not None:
        params["dataHoraAtualizacao"] = data_hora_atualizacao
    if empresa_codigo is not None:
        params["empresaCodigo"] = empresa_codigo
    if caixa_codigo is not None:
        params["caixaCodigo"] = caixa_codigo
    if funcionario_codigo is not None:
        params["funcionarioCodigo"] = funcionario_codigo
    if ultimo_codigo is not None:
        params["ultimoCodigo"] = ultimo_codigo
    if limite is not None:
        params["limite"] = limite
    result = client.get("/INTEGRACAO/SANGRIA_CAIXA", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def relatorio_pernonalizado(ultimo_codigo: Optional[int] = None, limite: Optional[int] = None) -> str:
    """relatorioPernonalizado - GET /INTEGRACAO/RELATORIO_PERSONALIZADO"""
    params = {}
    if ultimo_codigo is not None:
        params["ultimoCodigo"] = ultimo_codigo
    if limite is not None:
        params["limite"] = limite
    result = client.get("/INTEGRACAO/RELATORIO_PERSONALIZADO", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_produto_meta(grupo_meta_codigo: Optional[int] = None, ultimo_codigo: Optional[int] = None, limite: Optional[int] = None) -> str:
    """consultarProdutoMeta - GET /INTEGRACAO/PRODUTO_META"""
    params = {}
    if grupo_meta_codigo is not None:
        params["grupoMetaCodigo"] = grupo_meta_codigo
    if ultimo_codigo is not None:
        params["ultimoCodigo"] = ultimo_codigo
    if limite is not None:
        params["limite"] = limite
    result = client.get("/INTEGRACAO/PRODUTO_META", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_produto_lmc_lmp(codigo_produt_lmc: Optional[int] = None) -> str:
    """consultarProdutoLmcLmp - GET /INTEGRACAO/PRODUTO_LMC_LMP"""
    params = {}
    if codigo_produt_lmc is not None:
        params["codigoProdutLmc"] = codigo_produt_lmc
    result = client.get("/INTEGRACAO/PRODUTO_LMC_LMP", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_produto_estoque(empresa_codigo: int, data_hora: Optional[str] = None, grupo_codigo: Optional[list] = None, produto_codigo: Optional[list] = None) -> str:
    """consultarProdutoEstoque - GET /INTEGRACAO/PRODUTO_ESTOQUE"""
    params = {}
    if empresa_codigo is not None:
        params["empresaCodigo"] = empresa_codigo
    if data_hora is not None:
        params["dataHora"] = data_hora
    if grupo_codigo is not None:
        params["grupoCodigo"] = grupo_codigo
    if produto_codigo is not None:
        params["produtoCodigo"] = produto_codigo
    result = client.get("/INTEGRACAO/PRODUTO_ESTOQUE", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_produto_empresa(data_hora_atualizacao: Optional[str] = None, usa_produto_lmc: Optional[bool] = None, ultimo_codigo: Optional[int] = None, limite: Optional[int] = None) -> str:
    """consultarProdutoEmpresa - GET /INTEGRACAO/PRODUTO_EMPRESA"""
    params = {}
    if data_hora_atualizacao is not None:
        params["dataHoraAtualizacao"] = data_hora_atualizacao
    if usa_produto_lmc is not None:
        params["usaProdutoLmc"] = usa_produto_lmc
    if ultimo_codigo is not None:
        params["ultimoCodigo"] = ultimo_codigo
    if limite is not None:
        params["limite"] = limite
    result = client.get("/INTEGRACAO/PRODUTO_EMPRESA", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_produto(empresa_codigo: Optional[int] = None, produto_codigo: Optional[int] = None, produto_codigo_externo: Optional[str] = None, grupo_codigo: Optional[int] = None, usa_produto_lmc: Optional[bool] = None, ultimo_codigo: Optional[int] = None, limite: Optional[int] = None) -> str:
    """consultarProduto - GET /INTEGRACAO/PRODUTO"""
    params = {}
    if empresa_codigo is not None:
        params["empresaCodigo"] = empresa_codigo
    if produto_codigo is not None:
        params["produtoCodigo"] = produto_codigo
    if produto_codigo_externo is not None:
        params["produtoCodigoExterno"] = produto_codigo_externo
    if grupo_codigo is not None:
        params["grupoCodigo"] = grupo_codigo
    if usa_produto_lmc is not None:
        params["usaProdutoLmc"] = usa_produto_lmc
    if ultimo_codigo is not None:
        params["ultimoCodigo"] = ultimo_codigo
    if limite is not None:
        params["limite"] = limite
    result = client.get("/INTEGRACAO/PRODUTO", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_prazos(prazo_codigo: Optional[int] = None, prazo_codigo_externo: Optional[str] = None) -> str:
    """consultarPrazos - GET /INTEGRACAO/PRAZOS"""
    params = {}
    if prazo_codigo is not None:
        params["prazoCodigo"] = prazo_codigo
    if prazo_codigo_externo is not None:
        params["prazoCodigoExterno"] = prazo_codigo_externo
    result = client.get("/INTEGRACAO/PRAZOS", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_plano_conta_gerencial(plano_conta_codigo: Optional[int] = None, ultimo_codigo: Optional[int] = None, limite: Optional[int] = None) -> str:
    """consultarPlanoContaGerencial - GET /INTEGRACAO/PLANO_CONTA_GERENCIAL"""
    params = {}
    if plano_conta_codigo is not None:
        params["planoContaCodigo"] = plano_conta_codigo
    if ultimo_codigo is not None:
        params["ultimoCodigo"] = ultimo_codigo
    if limite is not None:
        params["limite"] = limite
    result = client.get("/INTEGRACAO/PLANO_CONTA_GERENCIAL", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_plano_conta_contabil(ultimo_codigo: Optional[int] = None, limite: Optional[int] = None) -> str:
    """consultarPlanoContaContabil - GET /INTEGRACAO/PLANO_CONTA_CONTABIL"""
    params = {}
    if ultimo_codigo is not None:
        params["ultimoCodigo"] = ultimo_codigo
    if limite is not None:
        params["limite"] = limite
    result = client.get("/INTEGRACAO/PLANO_CONTA_CONTABIL", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_placares(data_inicial: str, data_final: str) -> str:
    """consultarPlacares - GET /INTEGRACAO/PLACARES"""
    params = {}
    if data_inicial is not None:
        params["dataInicial"] = data_inicial
    if data_final is not None:
        params["dataFinal"] = data_final
    result = client.get("/INTEGRACAO/PLACARES", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_pisconfins(ultimo_codigo: Optional[int] = None, limite: Optional[int] = None) -> str:
    """consultarPisconfins - GET /INTEGRACAO/PIS_COFINS"""
    params = {}
    if ultimo_codigo is not None:
        params["ultimoCodigo"] = ultimo_codigo
    if limite is not None:
        params["limite"] = limite
    result = client.get("/INTEGRACAO/PIS_COFINS", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_trr_pedido(empresa_codigo: Optional[int] = None, data_inicial: Optional[str] = None, data_final: Optional[str] = None, ultimo_codigo: Optional[int] = None, limite: Optional[int] = None, pedido_codigo: Optional[int] = None) -> str:
    """consultarTrrPedido - GET /INTEGRACAO/PEDIDO_TRR"""
    params = {}
    if empresa_codigo is not None:
        params["empresaCodigo"] = empresa_codigo
    if data_inicial is not None:
        params["dataInicial"] = data_inicial
    if data_final is not None:
        params["dataFinal"] = data_final
    if ultimo_codigo is not None:
        params["ultimoCodigo"] = ultimo_codigo
    if limite is not None:
        params["limite"] = limite
    if pedido_codigo is not None:
        params["pedidoCodigo"] = pedido_codigo
    result = client.get("/INTEGRACAO/PEDIDO_TRR", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_pdv(pdv_referencia: Optional[str] = None, pdv_codigo: Optional[int] = None, empresa_codigo: Optional[int] = None, ultimo_codigo: Optional[int] = None, limite: Optional[int] = None) -> str:
    """consultarPdv - GET /INTEGRACAO/PDV"""
    params = {}
    if pdv_referencia is not None:
        params["pdvReferencia"] = pdv_referencia
    if pdv_codigo is not None:
        params["pdvCodigo"] = pdv_codigo
    if empresa_codigo is not None:
        params["empresaCodigo"] = empresa_codigo
    if ultimo_codigo is not None:
        params["ultimoCodigo"] = ultimo_codigo
    if limite is not None:
        params["limite"] = limite
    result = client.get("/INTEGRACAO/PDV", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_nfse(empresa_codigo: Optional[list] = None, data_inicial: Optional[str] = None, data_final: Optional[str] = None, nfse_codigo: Optional[int] = None, produto_codigo: Optional[int] = None, ultimo_codigo: Optional[int] = None, limite: Optional[int] = None) -> str:
    """consultarNfse - GET /INTEGRACAO/NOTA_SERVICO_ITEM"""
    params = {}
    if empresa_codigo is not None:
        params["empresaCodigo"] = empresa_codigo
    if data_inicial is not None:
        params["dataInicial"] = data_inicial
    if data_final is not None:
        params["dataFinal"] = data_final
    if nfse_codigo is not None:
        params["nfseCodigo"] = nfse_codigo
    if produto_codigo is not None:
        params["produtoCodigo"] = produto_codigo
    if ultimo_codigo is not None:
        params["ultimoCodigo"] = ultimo_codigo
    if limite is not None:
        params["limite"] = limite
    result = client.get("/INTEGRACAO/NOTA_SERVICO_ITEM", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_nfse_1(empresa_codigo: Optional[list] = None, data_inicial: Optional[str] = None, data_final: Optional[str] = None, fornecedor_codigo: Optional[int] = None, cliente_codigo: Optional[int] = None, nfse_codigo: Optional[int] = None, rps: Optional[str] = None, tipo_nota: Optional[str] = None, ultimo_codigo: Optional[int] = None, limite: Optional[int] = None) -> str:
    """consultarNfse_1 - GET /INTEGRACAO/NOTA_SERVICO"""
    params = {}
    if empresa_codigo is not None:
        params["empresaCodigo"] = empresa_codigo
    if data_inicial is not None:
        params["dataInicial"] = data_inicial
    if data_final is not None:
        params["dataFinal"] = data_final
    if fornecedor_codigo is not None:
        params["fornecedorCodigo"] = fornecedor_codigo
    if cliente_codigo is not None:
        params["clienteCodigo"] = cliente_codigo
    if nfse_codigo is not None:
        params["nfseCodigo"] = nfse_codigo
    if rps is not None:
        params["rps"] = rps
    if tipo_nota is not None:
        params["tipoNota"] = tipo_nota
    if ultimo_codigo is not None:
        params["ultimoCodigo"] = ultimo_codigo
    if limite is not None:
        params["limite"] = limite
    result = client.get("/INTEGRACAO/NOTA_SERVICO", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_nota_saida_item(data_inicial: Optional[str] = None, data_final: Optional[str] = None, empresa_codigo: Optional[int] = None, ultimo_codigo: Optional[int] = None, limite: Optional[int] = None, nota_codigo: Optional[int] = None, nota_item_codigo: Optional[int] = None) -> str:
    """consultarNotaSaidaItem - GET /INTEGRACAO/NOTA_SAIDA_ITEM"""
    params = {}
    if data_inicial is not None:
        params["dataInicial"] = data_inicial
    if data_final is not None:
        params["dataFinal"] = data_final
    if empresa_codigo is not None:
        params["empresaCodigo"] = empresa_codigo
    if ultimo_codigo is not None:
        params["ultimoCodigo"] = ultimo_codigo
    if limite is not None:
        params["limite"] = limite
    if nota_codigo is not None:
        params["notaCodigo"] = nota_codigo
    if nota_item_codigo is not None:
        params["notaItemCodigo"] = nota_item_codigo
    result = client.get("/INTEGRACAO/NOTA_SAIDA_ITEM", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_nota_manifestacao(data_inicial: Optional[str] = None, data_final: Optional[str] = None, compra_codigo: Optional[int] = None, empresa_codigo: Optional[int] = None, manifestacao_codigo: Optional[int] = None, ultimo_codigo: Optional[int] = None, limite: Optional[int] = None) -> str:
    """consultarNotaManifestacao - GET /INTEGRACAO/NOTA_MANIFESTACAO"""
    params = {}
    if data_inicial is not None:
        params["dataInicial"] = data_inicial
    if data_final is not None:
        params["dataFinal"] = data_final
    if compra_codigo is not None:
        params["compraCodigo"] = compra_codigo
    if empresa_codigo is not None:
        params["empresaCodigo"] = empresa_codigo
    if manifestacao_codigo is not None:
        params["manifestacaoCodigo"] = manifestacao_codigo
    if ultimo_codigo is not None:
        params["ultimoCodigo"] = ultimo_codigo
    if limite is not None:
        params["limite"] = limite
    result = client.get("/INTEGRACAO/NOTA_MANIFESTACAO", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_nfe_saida(data_inicial: str, data_final: str, chave_documento: Optional[str] = None, empresa_codigo: Optional[int] = None, ultimo_codigo: Optional[int] = None, limite: Optional[int] = None, situacao: Optional[str] = None, numero_documento: Optional[str] = None, serie_documento: Optional[str] = None, nota_codigo: Optional[list] = None, gerou_venda: Optional[bool] = None) -> str:
    """consultarNfeSaida - GET /INTEGRACAO/NFE_SAIDA"""
    params = {}
    if chave_documento is not None:
        params["chaveDocumento"] = chave_documento
    if data_inicial is not None:
        params["dataInicial"] = data_inicial
    if data_final is not None:
        params["dataFinal"] = data_final
    if empresa_codigo is not None:
        params["empresaCodigo"] = empresa_codigo
    if ultimo_codigo is not None:
        params["ultimoCodigo"] = ultimo_codigo
    if limite is not None:
        params["limite"] = limite
    if situacao is not None:
        params["situacao"] = situacao
    if numero_documento is not None:
        params["numeroDocumento"] = numero_documento
    if serie_documento is not None:
        params["serieDocumento"] = serie_documento
    if nota_codigo is not None:
        params["notaCodigo"] = nota_codigo
    if gerou_venda is not None:
        params["gerouVenda"] = gerou_venda
    result = client.get("/INTEGRACAO/NFE_SAIDA", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consulta_nfe_xml(id: Optional[int] = None, modelo_documento: Optional[int] = None, numero_documento: Optional[int] = None, empresa_codigo: Optional[int] = None, serie_documento: Optional[int] = None, situacao: Optional[str] = None) -> str:
    """consultaNfeXml - GET /INTEGRACAO/NFE/XML"""
    params = {}
    if id is not None:
        params["id"] = id
    if modelo_documento is not None:
        params["modeloDocumento"] = modelo_documento
    if numero_documento is not None:
        params["numeroDocumento"] = numero_documento
    if empresa_codigo is not None:
        params["empresaCodigo"] = empresa_codigo
    if serie_documento is not None:
        params["serieDocumento"] = serie_documento
    if situacao is not None:
        params["situacao"] = situacao
    result = client.get("/INTEGRACAO/NFE/XML", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_nfce(data_inicial: str, data_final: str, empresa_codigo: Optional[list] = None, venda_codigo: Optional[int] = None, ultimo_codigo: Optional[int] = None, limite: Optional[int] = None, situacao: Optional[str] = None) -> str:
    """consultarNfce - GET /INTEGRACAO/NFCE"""
    params = {}
    if empresa_codigo is not None:
        params["empresaCodigo"] = empresa_codigo
    if data_inicial is not None:
        params["dataInicial"] = data_inicial
    if data_final is not None:
        params["dataFinal"] = data_final
    if venda_codigo is not None:
        params["vendaCodigo"] = venda_codigo
    if ultimo_codigo is not None:
        params["ultimoCodigo"] = ultimo_codigo
    if limite is not None:
        params["limite"] = limite
    if situacao is not None:
        params["situacao"] = situacao
    result = client.get("/INTEGRACAO/NFCE", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consult_nfcea_xml(id: str, modelo_documento: int, numero_documento: int, empresa_codigo: int, serie_documento: int) -> str:
    """consultNfceaXml - GET /INTEGRACAO/NFCE/{id}/XML"""
    params = {}
    if modelo_documento is not None:
        params["modeloDocumento"] = modelo_documento
    if numero_documento is not None:
        params["numeroDocumento"] = numero_documento
    if empresa_codigo is not None:
        params["empresaCodigo"] = empresa_codigo
    if serie_documento is not None:
        params["serieDocumento"] = serie_documento
    result = client.get("/INTEGRACAO/NFCE/{id}/XML", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_relatorio_mapa(data_inicial: str, data_final: str, empresa_codigo: Optional[list] = None, venda_codigo: Optional[int] = None, ultimo_codigo: Optional[int] = None, limite: Optional[int] = None, quitado: Optional[bool] = None, data_hora_atualizacao: Optional[str] = None, origem: Optional[str] = None) -> str:
    """consultarRelatorioMapa - GET /INTEGRACAO/MAPA_DESEMPENHO"""
    params = {}
    if empresa_codigo is not None:
        params["empresaCodigo"] = empresa_codigo
    if data_inicial is not None:
        params["dataInicial"] = data_inicial
    if data_final is not None:
        params["dataFinal"] = data_final
    if venda_codigo is not None:
        params["vendaCodigo"] = venda_codigo
    if ultimo_codigo is not None:
        params["ultimoCodigo"] = ultimo_codigo
    if limite is not None:
        params["limite"] = limite
    if quitado is not None:
        params["quitado"] = quitado
    if data_hora_atualizacao is not None:
        params["dataHoraAtualizacao"] = data_hora_atualizacao
    if origem is not None:
        params["origem"] = origem
    result = client.get("/INTEGRACAO/MAPA_DESEMPENHO", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_icms(ultimo_codigo: Optional[int] = None, limite: Optional[int] = None) -> str:
    """consultarIcms - GET /INTEGRACAO/ICMS"""
    params = {}
    if ultimo_codigo is not None:
        params["ultimoCodigo"] = ultimo_codigo
    if limite is not None:
        params["limite"] = limite
    result = client.get("/INTEGRACAO/ICMS", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_grupo_meta(ultimo_codigo: Optional[int] = None, limite: Optional[int] = None) -> str:
    """consultarGrupoMeta - GET /INTEGRACAO/GRUPO_META"""
    params = {}
    if ultimo_codigo is not None:
        params["ultimoCodigo"] = ultimo_codigo
    if limite is not None:
        params["limite"] = limite
    result = client.get("/INTEGRACAO/GRUPO_META", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_grupo(grupo_codigo_externo: Optional[str] = None, ultimo_codigo: Optional[int] = None, limite: Optional[int] = None) -> str:
    """consultarGrupo - GET /INTEGRACAO/GRUPO"""
    params = {}
    if grupo_codigo_externo is not None:
        params["grupoCodigoExterno"] = grupo_codigo_externo
    if ultimo_codigo is not None:
        params["ultimoCodigo"] = ultimo_codigo
    if limite is not None:
        params["limite"] = limite
    result = client.get("/INTEGRACAO/GRUPO", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_funcoes(ultimo_codigo: Optional[int] = None, limite: Optional[int] = None) -> str:
    """consultarFuncoes - GET /INTEGRACAO/FUNCOES"""
    params = {}
    if ultimo_codigo is not None:
        params["ultimoCodigo"] = ultimo_codigo
    if limite is not None:
        params["limite"] = limite
    result = client.get("/INTEGRACAO/FUNCOES", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_funcionario_meta(grupo_meta_codigo: Optional[int] = None, ultimo_codigo: Optional[int] = None, limite: Optional[int] = None) -> str:
    """consultarFuncionarioMeta - GET /INTEGRACAO/FUNCIONARIO_META"""
    params = {}
    if grupo_meta_codigo is not None:
        params["grupoMetaCodigo"] = grupo_meta_codigo
    if ultimo_codigo is not None:
        params["ultimoCodigo"] = ultimo_codigo
    if limite is not None:
        params["limite"] = limite
    result = client.get("/INTEGRACAO/FUNCIONARIO_META", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_funcionario(funcionario_codigo: Optional[int] = None, empresa_codigo: Optional[int] = None, ultimo_codigo: Optional[int] = None, limite: Optional[int] = None) -> str:
    """consultarFuncionario - GET /INTEGRACAO/FUNCIONARIO"""
    params = {}
    if funcionario_codigo is not None:
        params["funcionarioCodigo"] = funcionario_codigo
    if empresa_codigo is not None:
        params["empresaCodigo"] = empresa_codigo
    if ultimo_codigo is not None:
        params["ultimoCodigo"] = ultimo_codigo
    if limite is not None:
        params["limite"] = limite
    result = client.get("/INTEGRACAO/FUNCIONARIO", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_fornecedor(retorna_observacoes: Optional[bool] = None, data_hora_atualizacao: Optional[str] = None, fornecedor_codigo_externo: Optional[str] = None, fornecedor_codigo: Optional[int] = None, cnpj_cpf: Optional[str] = None, ultimo_codigo: Optional[int] = None, limite: Optional[int] = None) -> str:
    """consultarFornecedor - GET /INTEGRACAO/FORNECEDOR"""
    params = {}
    if retorna_observacoes is not None:
        params["retornaObservacoes"] = retorna_observacoes
    if data_hora_atualizacao is not None:
        params["dataHoraAtualizacao"] = data_hora_atualizacao
    if fornecedor_codigo_externo is not None:
        params["fornecedorCodigoExterno"] = fornecedor_codigo_externo
    if fornecedor_codigo is not None:
        params["fornecedorCodigo"] = fornecedor_codigo
    if cnpj_cpf is not None:
        params["cnpjCpf"] = cnpj_cpf
    if ultimo_codigo is not None:
        params["ultimoCodigo"] = ultimo_codigo
    if limite is not None:
        params["limite"] = limite
    result = client.get("/INTEGRACAO/FORNECEDOR", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_forma_pagamento(ultimo_codigo: Optional[int] = None, limite: Optional[int] = None) -> str:
    """consultarFormaPagamento - GET /INTEGRACAO/FORMA_PAGAMENTO"""
    params = {}
    if ultimo_codigo is not None:
        params["ultimoCodigo"] = ultimo_codigo
    if limite is not None:
        params["limite"] = limite
    result = client.get("/INTEGRACAO/FORMA_PAGAMENTO", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_esclusao_financeiro(empresa_codigo: Optional[int] = None, data_hora_inicial: Optional[str] = None, data_hora_final: Optional[str] = None, ultimo_codigo: Optional[int] = None, limite: Optional[int] = None) -> str:
    """consultarEsclusaoFinanceiro - GET /INTEGRACAO/FINANCEIRO_EXCLUSAO"""
    params = {}
    if empresa_codigo is not None:
        params["empresaCodigo"] = empresa_codigo
    if data_hora_inicial is not None:
        params["dataHoraInicial"] = data_hora_inicial
    if data_hora_final is not None:
        params["dataHoraFinal"] = data_hora_final
    if ultimo_codigo is not None:
        params["ultimoCodigo"] = ultimo_codigo
    if limite is not None:
        params["limite"] = limite
    result = client.get("/INTEGRACAO/FINANCEIRO_EXCLUSAO", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def estoque_periodo(data_final: str, empresa_codigo: Optional[int] = None, data_hora_atualizacao: Optional[str] = None, ultimo_codigo: Optional[int] = None, limite: Optional[int] = None) -> str:
    """estoquePeriodo - GET /INTEGRACAO/ESTOQUE_PERIODO"""
    params = {}
    if data_final is not None:
        params["dataFinal"] = data_final
    if empresa_codigo is not None:
        params["empresaCodigo"] = empresa_codigo
    if data_hora_atualizacao is not None:
        params["dataHoraAtualizacao"] = data_hora_atualizacao
    if ultimo_codigo is not None:
        params["ultimoCodigo"] = ultimo_codigo
    if limite is not None:
        params["limite"] = limite
    result = client.get("/INTEGRACAO/ESTOQUE_PERIODO", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def estoque(empresa_codigo: Optional[int] = None, data_hora_atualizacao: Optional[str] = None, estoque_codigo: Optional[int] = None, estoque_codigo_externo: Optional[str] = None, ultimo_codigo: Optional[int] = None, limite: Optional[int] = None) -> str:
    """estoque - GET /INTEGRACAO/ESTOQUE"""
    params = {}
    if empresa_codigo is not None:
        params["empresaCodigo"] = empresa_codigo
    if data_hora_atualizacao is not None:
        params["dataHoraAtualizacao"] = data_hora_atualizacao
    if estoque_codigo is not None:
        params["estoqueCodigo"] = estoque_codigo
    if estoque_codigo_externo is not None:
        params["estoqueCodigoExterno"] = estoque_codigo_externo
    if ultimo_codigo is not None:
        params["ultimoCodigo"] = ultimo_codigo
    if limite is not None:
        params["limite"] = limite
    result = client.get("/INTEGRACAO/ESTOQUE", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_empresa(empresa_codigo_externo: Optional[str] = None, ultimo_codigo: Optional[int] = None, limite: Optional[int] = None) -> str:
    """consultarEmpresa - GET /INTEGRACAO/EMPRESAS"""
    params = {}
    if empresa_codigo_externo is not None:
        params["empresaCodigoExterno"] = empresa_codigo_externo
    if ultimo_codigo is not None:
        params["ultimoCodigo"] = ultimo_codigo
    if limite is not None:
        params["limite"] = limite
    result = client.get("/INTEGRACAO/EMPRESAS", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_duplicata(data_inicial: Optional[str] = None, data_final: Optional[str] = None, data_hora_atualizacao: Optional[str] = None, apenas_pendente: Optional[bool] = None, data_filtro: Optional[str] = None, ultimo_codigo: Optional[int] = None, limite: Optional[int] = None, empresa_codigo: Optional[int] = None, nota_entrada_codigo: Optional[int] = None, titulo_pagar_codigo: Optional[int] = None, fornecedor_codigo: Optional[int] = None, linha_digitavel: Optional[str] = None, autorizado: Optional[bool] = None, tipo_lancamento: Optional[str] = None) -> str:
    """consultarDuplicata - GET /INTEGRACAO/DUPLICATA"""
    params = {}
    if data_inicial is not None:
        params["dataInicial"] = data_inicial
    if data_final is not None:
        params["dataFinal"] = data_final
    if data_hora_atualizacao is not None:
        params["dataHoraAtualizacao"] = data_hora_atualizacao
    if apenas_pendente is not None:
        params["apenasPendente"] = apenas_pendente
    if data_filtro is not None:
        params["dataFiltro"] = data_filtro
    if ultimo_codigo is not None:
        params["ultimoCodigo"] = ultimo_codigo
    if limite is not None:
        params["limite"] = limite
    if empresa_codigo is not None:
        params["empresaCodigo"] = empresa_codigo
    if nota_entrada_codigo is not None:
        params["notaEntradaCodigo"] = nota_entrada_codigo
    if titulo_pagar_codigo is not None:
        params["tituloPagarCodigo"] = titulo_pagar_codigo
    if fornecedor_codigo is not None:
        params["fornecedorCodigo"] = fornecedor_codigo
    if linha_digitavel is not None:
        params["linhaDigitavel"] = linha_digitavel
    if autorizado is not None:
        params["autorizado"] = autorizado
    if tipo_lancamento is not None:
        params["tipoLancamento"] = tipo_lancamento
    result = client.get("/INTEGRACAO/DUPLICATA", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_dre(data_inicial: str, data_final: str, apuracao_caixa: Optional[bool] = None, cfop_outras_saidas: Optional[bool] = None, apurar_juros_descontos: Optional[bool] = None, filiais: Optional[list] = None, centro_custo_codigo: Optional[list] = None, apurar_centro_custo_produto: Optional[bool] = None) -> str:
    """consultarDre - GET /INTEGRACAO/DRE"""
    params = {}
    if apuracao_caixa is not None:
        params["apuracaoCaixa"] = apuracao_caixa
    if data_inicial is not None:
        params["dataInicial"] = data_inicial
    if data_final is not None:
        params["dataFinal"] = data_final
    if cfop_outras_saidas is not None:
        params["cfopOutrasSaidas"] = cfop_outras_saidas
    if apurar_juros_descontos is not None:
        params["apurarJurosDescontos"] = apurar_juros_descontos
    if filiais is not None:
        params["filiais"] = filiais
    if centro_custo_codigo is not None:
        params["centroCustoCodigo"] = centro_custo_codigo
    if apurar_centro_custo_produto is not None:
        params["apurarCentroCustoProduto"] = apurar_centro_custo_produto
    result = client.get("/INTEGRACAO/DRE", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def dfe_xml(modelo_documento: int, numero_documento: int, empresa_codigo: int, serie_documento: int) -> str:
    """dfeXml - GET /INTEGRACAO/DFE_XML"""
    params = {}
    if modelo_documento is not None:
        params["modeloDocumento"] = modelo_documento
    if numero_documento is not None:
        params["numeroDocumento"] = numero_documento
    if empresa_codigo is not None:
        params["empresaCodigo"] = empresa_codigo
    if serie_documento is not None:
        params["serieDocumento"] = serie_documento
    result = client.get("/INTEGRACAO/DFE_XML", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_conta(empresa_codigo: Optional[int] = None, ultimo_codigo: Optional[int] = None, limite: Optional[int] = None) -> str:
    """consultarConta - GET /INTEGRACAO/CONTA"""
    params = {}
    if empresa_codigo is not None:
        params["empresaCodigo"] = empresa_codigo
    if ultimo_codigo is not None:
        params["ultimoCodigo"] = ultimo_codigo
    if limite is not None:
        params["limite"] = limite
    result = client.get("/INTEGRACAO/CONTA", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_contagem_estoque(data_contagem: str, contagem_referencia: Optional[int] = None, ultimo_codigo: Optional[int] = None, limite: Optional[int] = None) -> str:
    """consultarContagemEstoque - GET /INTEGRACAO/CONTAGEM_ESTOQUE"""
    params = {}
    if data_contagem is not None:
        params["dataContagem"] = data_contagem
    if contagem_referencia is not None:
        params["contagemReferencia"] = contagem_referencia
    if ultimo_codigo is not None:
        params["ultimoCodigo"] = ultimo_codigo
    if limite is not None:
        params["limite"] = limite
    result = client.get("/INTEGRACAO/CONTAGEM_ESTOQUE", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consumo_cliente(token: str, data_inicial: Optional[str] = None, data_final: Optional[str] = None, ultimo_codigo: Optional[int] = None, limite: Optional[int] = None) -> str:
    """consumoCliente - GET /INTEGRACAO/CONSUMO_CLIENTE"""
    params = {}
    if token is not None:
        params["token"] = token
    if data_inicial is not None:
        params["dataInicial"] = data_inicial
    if data_final is not None:
        params["dataFinal"] = data_final
    if ultimo_codigo is not None:
        params["ultimoCodigo"] = ultimo_codigo
    if limite is not None:
        params["limite"] = limite
    result = client.get("/INTEGRACAO/CONSUMO_CLIENTE", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_view(dias: Optional[int] = None, volume_minimo: Optional[int] = None, view: Optional[str] = None) -> str:
    """consultarView - GET /INTEGRACAO/CONSULTAR_VIEW"""
    params = {}
    if dias is not None:
        params["dias"] = dias
    if volume_minimo is not None:
        params["volumeMinimo"] = volume_minimo
    if view is not None:
        params["view"] = view
    result = client.get("/INTEGRACAO/CONSULTAR_VIEW", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_sub_grupo_rede() -> str:
    """consultarSubGrupoRede - GET /INTEGRACAO/CONSULTAR_SUB_GRUPO_REDE"""
    params = {}

    result = client.get("/INTEGRACAO/CONSULTAR_SUB_GRUPO_REDE", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_sub_grupo_rede_1() -> str:
    """consultarSubGrupoRede_1 - GET /INTEGRACAO/SUB_GRUPO_REDE"""
    params = {}

    result = client.get("/INTEGRACAO/SUB_GRUPO_REDE", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_preco_idenfitid() -> str:
    """consultarPrecoIdenfitid - GET /INTEGRACAO/CONSULTAR_PRECO_IDENTIFID"""
    params = {}

    result = client.get("/INTEGRACAO/CONSULTAR_PRECO_IDENTIFID", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_lmc(data_inicial: str, data_final: str, empresa_codigo: Optional[list] = None, venda_codigo: Optional[int] = None, ultimo_codigo: Optional[int] = None, limite: Optional[int] = None, quitado: Optional[bool] = None, data_hora_atualizacao: Optional[str] = None, origem: Optional[str] = None) -> str:
    """consultarLmc - GET /INTEGRACAO/CONSULTAR_LMC_REDE"""
    params = {}
    if empresa_codigo is not None:
        params["empresaCodigo"] = empresa_codigo
    if data_inicial is not None:
        params["dataInicial"] = data_inicial
    if data_final is not None:
        params["dataFinal"] = data_final
    if venda_codigo is not None:
        params["vendaCodigo"] = venda_codigo
    if ultimo_codigo is not None:
        params["ultimoCodigo"] = ultimo_codigo
    if limite is not None:
        params["limite"] = limite
    if quitado is not None:
        params["quitado"] = quitado
    if data_hora_atualizacao is not None:
        params["dataHoraAtualizacao"] = data_hora_atualizacao
    if origem is not None:
        params["origem"] = origem
    result = client.get("/INTEGRACAO/CONSULTAR_LMC_REDE", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_lmc_1(data_inicial: str, data_final: str, empresa_codigo: Optional[list] = None, venda_codigo: Optional[int] = None, ultimo_codigo: Optional[int] = None, limite: Optional[int] = None, quitado: Optional[bool] = None, data_hora_atualizacao: Optional[str] = None, origem: Optional[str] = None) -> str:
    """consultarLmc_1 - GET /INTEGRACAO/LMC"""
    params = {}
    if empresa_codigo is not None:
        params["empresaCodigo"] = empresa_codigo
    if data_inicial is not None:
        params["dataInicial"] = data_inicial
    if data_final is not None:
        params["dataFinal"] = data_final
    if venda_codigo is not None:
        params["vendaCodigo"] = venda_codigo
    if ultimo_codigo is not None:
        params["ultimoCodigo"] = ultimo_codigo
    if limite is not None:
        params["limite"] = limite
    if quitado is not None:
        params["quitado"] = quitado
    if data_hora_atualizacao is not None:
        params["dataHoraAtualizacao"] = data_hora_atualizacao
    if origem is not None:
        params["origem"] = origem
    result = client.get("/INTEGRACAO/LMC", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_funcionario_idenfitid() -> str:
    """consultarFuncionarioIdenfitid - GET /INTEGRACAO/CONSULTAR_FUNCIONARIO_IDENTFID"""
    params = {}

    result = client.get("/INTEGRACAO/CONSULTAR_FUNCIONARIO_IDENTFID", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_despesa_financeiro_rede(data_inicial: str, data_final: str, apuracao_caixa: Optional[bool] = None) -> str:
    """consultarDespesaFinanceiroRede - GET /INTEGRACAO/CONSULTAR_DESPESAS_FINANCEIRO_REDE"""
    params = {}
    if data_inicial is not None:
        params["dataInicial"] = data_inicial
    if data_final is not None:
        params["dataFinal"] = data_final
    if apuracao_caixa is not None:
        params["apuracaoCaixa"] = apuracao_caixa
    result = client.get("/INTEGRACAO/CONSULTAR_DESPESAS_FINANCEIRO_REDE", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_cartoes_clubgas(nome_tabela: str) -> str:
    """consultarCartoesClubgas - GET /INTEGRACAO/CONSULTAR_CARTOES_CLUBGAS"""
    params = {}
    if nome_tabela is not None:
        params["nomeTabela"] = nome_tabela
    result = client.get("/INTEGRACAO/CONSULTAR_CARTOES_CLUBGAS", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_compra_item(turno: Optional[int] = None, empresa_codigo: Optional[int] = None, usa_produto_lmc: Optional[bool] = None, compra_codigo: Optional[int] = None, data_inicial: Optional[str] = None, data_final: Optional[str] = None, tipo_data: Optional[str] = None, ultimo_codigo: Optional[int] = None, limite: Optional[int] = None, situacao: Optional[str] = None) -> str:
    """consultarCompraItem - GET /INTEGRACAO/COMPRA_ITEM"""
    params = {}
    if turno is not None:
        params["turno"] = turno
    if empresa_codigo is not None:
        params["empresaCodigo"] = empresa_codigo
    if usa_produto_lmc is not None:
        params["usaProdutoLmc"] = usa_produto_lmc
    if compra_codigo is not None:
        params["compraCodigo"] = compra_codigo
    if data_inicial is not None:
        params["dataInicial"] = data_inicial
    if data_final is not None:
        params["dataFinal"] = data_final
    if tipo_data is not None:
        params["tipoData"] = tipo_data
    if ultimo_codigo is not None:
        params["ultimoCodigo"] = ultimo_codigo
    if limite is not None:
        params["limite"] = limite
    if situacao is not None:
        params["situacao"] = situacao
    result = client.get("/INTEGRACAO/COMPRA_ITEM", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_compra(turno: Optional[int] = None, empresa_codigo: Optional[int] = None, data_inicial: Optional[str] = None, data_final: Optional[str] = None, tipo_data: Optional[str] = None, nota_serie: Optional[str] = None, nota_numero: Optional[str] = None, ultimo_codigo: Optional[int] = None, limite: Optional[int] = None, venda_codigo: Optional[list] = None, situacao: Optional[str] = None) -> str:
    """consultarCompra - GET /INTEGRACAO/COMPRA"""
    params = {}
    if turno is not None:
        params["turno"] = turno
    if empresa_codigo is not None:
        params["empresaCodigo"] = empresa_codigo
    if data_inicial is not None:
        params["dataInicial"] = data_inicial
    if data_final is not None:
        params["dataFinal"] = data_final
    if tipo_data is not None:
        params["tipoData"] = tipo_data
    if nota_serie is not None:
        params["notaSerie"] = nota_serie
    if nota_numero is not None:
        params["notaNumero"] = nota_numero
    if ultimo_codigo is not None:
        params["ultimoCodigo"] = ultimo_codigo
    if limite is not None:
        params["limite"] = limite
    if venda_codigo is not None:
        params["vendaCodigo"] = venda_codigo
    if situacao is not None:
        params["situacao"] = situacao
    result = client.get("/INTEGRACAO/COMPRA", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_compra_xml(chave_nfe: str) -> str:
    """consultarCompraXml - GET /INTEGRACAO/COMPRA/{chaveNfe}/XML"""
    params = {}

    result = client.get("/INTEGRACAO/COMPRA/{chaveNfe}/XML", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def cliente_frota(cliente_codigo_externo: Optional[str] = None, cliente_codigo: Optional[list] = None, motorista_codigo: Optional[list] = None, ultimo_codigo: Optional[int] = None, limite: Optional[int] = None) -> str:
    """clienteFrota - GET /INTEGRACAO/CLIENTE_FROTA"""
    params = {}
    if cliente_codigo_externo is not None:
        params["clienteCodigoExterno"] = cliente_codigo_externo
    if cliente_codigo is not None:
        params["clienteCodigo"] = cliente_codigo
    if motorista_codigo is not None:
        params["motoristaCodigo"] = motorista_codigo
    if ultimo_codigo is not None:
        params["ultimoCodigo"] = ultimo_codigo
    if limite is not None:
        params["limite"] = limite
    result = client.get("/INTEGRACAO/CLIENTE_FROTA", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_cliente_empresa(ultimo_codigo: Optional[int] = None, limite: Optional[int] = None) -> str:
    """consultarClienteEmpresa - GET /INTEGRACAO/CLIENTE_EMPRESA"""
    params = {}
    if ultimo_codigo is not None:
        params["ultimoCodigo"] = ultimo_codigo
    if limite is not None:
        params["limite"] = limite
    result = client.get("/INTEGRACAO/CLIENTE_EMPRESA", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_cheque_pagar(data_inicial: str, data_final: str, tipo_data: str, empresa_codigo: Optional[int] = None, situacao: Optional[str] = None, cheque_troco: Optional[bool] = None, cheque_codigo: Optional[int] = None, conta_codigo: Optional[int] = None, caixa_codigo: Optional[int] = None, tipo_inclusao: Optional[str] = None, ultimo_codigo: Optional[int] = None, limite: Optional[int] = None) -> str:
    """consultarChequePagar - GET /INTEGRACAO/CHEQUE_PAGAR"""
    params = {}
    if empresa_codigo is not None:
        params["empresaCodigo"] = empresa_codigo
    if data_inicial is not None:
        params["dataInicial"] = data_inicial
    if data_final is not None:
        params["dataFinal"] = data_final
    if tipo_data is not None:
        params["tipoData"] = tipo_data
    if situacao is not None:
        params["situacao"] = situacao
    if cheque_troco is not None:
        params["chequeTroco"] = cheque_troco
    if cheque_codigo is not None:
        params["chequeCodigo"] = cheque_codigo
    if conta_codigo is not None:
        params["contaCodigo"] = conta_codigo
    if caixa_codigo is not None:
        params["caixaCodigo"] = caixa_codigo
    if tipo_inclusao is not None:
        params["tipoInclusao"] = tipo_inclusao
    if ultimo_codigo is not None:
        params["ultimoCodigo"] = ultimo_codigo
    if limite is not None:
        params["limite"] = limite
    result = client.get("/INTEGRACAO/CHEQUE_PAGAR", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_cheque(data_inicial: str, data_final: str, turno: Optional[int] = None, empresa_codigo: Optional[int] = None, apenas_pendente: Optional[bool] = None, data_filtro: Optional[str] = None, ultimo_codigo: Optional[int] = None, limite: Optional[int] = None, data_hora_atualizacao: Optional[str] = None, venda_codigo: Optional[list] = None) -> str:
    """consultarCheque - GET /INTEGRACAO/CHEQUE"""
    params = {}
    if turno is not None:
        params["turno"] = turno
    if empresa_codigo is not None:
        params["empresaCodigo"] = empresa_codigo
    if data_inicial is not None:
        params["dataInicial"] = data_inicial
    if data_final is not None:
        params["dataFinal"] = data_final
    if apenas_pendente is not None:
        params["apenasPendente"] = apenas_pendente
    if data_filtro is not None:
        params["dataFiltro"] = data_filtro
    if ultimo_codigo is not None:
        params["ultimoCodigo"] = ultimo_codigo
    if limite is not None:
        params["limite"] = limite
    if data_hora_atualizacao is not None:
        params["dataHoraAtualizacao"] = data_hora_atualizacao
    if venda_codigo is not None:
        params["vendaCodigo"] = venda_codigo
    result = client.get("/INTEGRACAO/CHEQUE", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_centro_custo(centro_custo_codigo_externo: Optional[str] = None, ultimo_codigo: Optional[int] = None, limite: Optional[int] = None) -> str:
    """consultarCentroCusto - GET /INTEGRACAO/CENTRO_CUSTO"""
    params = {}
    if centro_custo_codigo_externo is not None:
        params["centroCustoCodigoExterno"] = centro_custo_codigo_externo
    if ultimo_codigo is not None:
        params["ultimoCodigo"] = ultimo_codigo
    if limite is not None:
        params["limite"] = limite
    result = client.get("/INTEGRACAO/CENTRO_CUSTO", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_pisconfins_1(data_inicial: str, data_final: str, empresa_codigo: Optional[list] = None, venda_codigo: Optional[int] = None, ultimo_codigo: Optional[int] = None, limite: Optional[int] = None, quitado: Optional[bool] = None, data_hora_atualizacao: Optional[str] = None, origem: Optional[str] = None) -> str:
    """consultarPisconfins_1 - GET /INTEGRACAO/CARTAO_REMESSA"""
    params = {}
    if empresa_codigo is not None:
        params["empresaCodigo"] = empresa_codigo
    if data_inicial is not None:
        params["dataInicial"] = data_inicial
    if data_final is not None:
        params["dataFinal"] = data_final
    if venda_codigo is not None:
        params["vendaCodigo"] = venda_codigo
    if ultimo_codigo is not None:
        params["ultimoCodigo"] = ultimo_codigo
    if limite is not None:
        params["limite"] = limite
    if quitado is not None:
        params["quitado"] = quitado
    if data_hora_atualizacao is not None:
        params["dataHoraAtualizacao"] = data_hora_atualizacao
    if origem is not None:
        params["origem"] = origem
    result = client.get("/INTEGRACAO/CARTAO_REMESSA", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_cartao_pagar(data_inicial: str, data_final: str, tipo_data: str, empresa_codigo: Optional[int] = None, cartao_compra_codigo: Optional[int] = None, situacao: Optional[str] = None, autorizacao: Optional[str] = None, ultimo_codigo: Optional[int] = None, limite: Optional[int] = None) -> str:
    """consultarCartaoPagar - GET /INTEGRACAO/CARTAO_PAGAR"""
    params = {}
    if empresa_codigo is not None:
        params["empresaCodigo"] = empresa_codigo
    if data_inicial is not None:
        params["dataInicial"] = data_inicial
    if data_final is not None:
        params["dataFinal"] = data_final
    if tipo_data is not None:
        params["tipoData"] = tipo_data
    if cartao_compra_codigo is not None:
        params["cartaoCompraCodigo"] = cartao_compra_codigo
    if situacao is not None:
        params["situacao"] = situacao
    if autorizacao is not None:
        params["autorizacao"] = autorizacao
    if ultimo_codigo is not None:
        params["ultimoCodigo"] = ultimo_codigo
    if limite is not None:
        params["limite"] = limite
    result = client.get("/INTEGRACAO/CARTAO_PAGAR", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_cheque_pagar_1(cartao_compra_codigo: Optional[int] = None, empresa_codigo: Optional[int] = None, ultimo_codigo: Optional[int] = None, limite: Optional[int] = None) -> str:
    """consultarChequePagar_1 - GET /INTEGRACAO/CARTAO_COMPRA"""
    params = {}
    if cartao_compra_codigo is not None:
        params["cartaoCompraCodigo"] = cartao_compra_codigo
    if empresa_codigo is not None:
        params["empresaCodigo"] = empresa_codigo
    if ultimo_codigo is not None:
        params["ultimoCodigo"] = ultimo_codigo
    if limite is not None:
        params["limite"] = limite
    result = client.get("/INTEGRACAO/CARTAO_COMPRA", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_caixa_apresentado(data_inicial: str, data_final: str, data_hora_atualizacao: Optional[str] = None, tipo_data: Optional[str] = None, ultimo_codigo: Optional[int] = None, limite: Optional[int] = None) -> str:
    """consultarCaixaApresentado - GET /INTEGRACAO/CAIXA_APRESENTADO"""
    params = {}
    if data_inicial is not None:
        params["dataInicial"] = data_inicial
    if data_final is not None:
        params["dataFinal"] = data_final
    if data_hora_atualizacao is not None:
        params["dataHoraAtualizacao"] = data_hora_atualizacao
    if tipo_data is not None:
        params["tipoData"] = tipo_data
    if ultimo_codigo is not None:
        params["ultimoCodigo"] = ultimo_codigo
    if limite is not None:
        params["limite"] = limite
    result = client.get("/INTEGRACAO/CAIXA_APRESENTADO", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_caixa(data_inicial: str, data_final: str, turno: Optional[int] = None, empresa_codigo: Optional[int] = None, individual: Optional[bool] = None, ultimo_codigo: Optional[int] = None, limite: Optional[int] = None) -> str:
    """consultarCaixa - GET /INTEGRACAO/CAIXA"""
    params = {}
    if data_inicial is not None:
        params["dataInicial"] = data_inicial
    if data_final is not None:
        params["dataFinal"] = data_final
    if turno is not None:
        params["turno"] = turno
    if empresa_codigo is not None:
        params["empresaCodigo"] = empresa_codigo
    if individual is not None:
        params["individual"] = individual
    if ultimo_codigo is not None:
        params["ultimoCodigo"] = ultimo_codigo
    if limite is not None:
        params["limite"] = limite
    result = client.get("/INTEGRACAO/CAIXA", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_bomba(bomba_codigo: Optional[int] = None, empresa_codigo: Optional[int] = None) -> str:
    """consultarBomba - GET /INTEGRACAO/BOMBA"""
    params = {}
    if bomba_codigo is not None:
        params["bombaCodigo"] = bomba_codigo
    if empresa_codigo is not None:
        params["empresaCodigo"] = empresa_codigo
    result = client.get("/INTEGRACAO/BOMBA", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_bico(bico_codigo: Optional[int] = None, empresa_codigo: Optional[int] = None, ultimo_codigo: Optional[int] = None, limite: Optional[int] = None) -> str:
    """consultarBico - GET /INTEGRACAO/BICO"""
    params = {}
    if bico_codigo is not None:
        params["bicoCodigo"] = bico_codigo
    if empresa_codigo is not None:
        params["empresaCodigo"] = empresa_codigo
    if ultimo_codigo is not None:
        params["ultimoCodigo"] = ultimo_codigo
    if limite is not None:
        params["limite"] = limite
    result = client.get("/INTEGRACAO/BICO", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def aprix_preco_cliente() -> str:
    """aprixPrecoCliente - GET /INTEGRACAO/APRIX_PRECO_CLIENTE"""
    params = {}

    result = client.get("/INTEGRACAO/APRIX_PRECO_CLIENTE", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def aprix_movimento(data_inicial: str, data_final: str) -> str:
    """aprixMovimento - GET /INTEGRACAO/APRIX_MOVIMENTO"""
    params = {}
    if data_inicial is not None:
        params["DATA_INICIAL"] = data_inicial
    if data_final is not None:
        params["DATA_FINAL"] = data_final
    result = client.get("/INTEGRACAO/APRIX_MOVIMENTO", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def aprix_custo(data_inicial: str, data_final: str) -> str:
    """aprixCusto - GET /INTEGRACAO/APRIX_CUSTO"""
    params = {}
    if data_inicial is not None:
        params["DATA_INICIAL"] = data_inicial
    if data_final is not None:
        params["DATA_FINAL"] = data_final
    result = client.get("/INTEGRACAO/APRIX_CUSTO", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_administradora(administradora_codigo: Optional[int] = None, empresa_codigo: Optional[int] = None, administradora_codigo_externo: Optional[str] = None, ultimo_codigo: Optional[int] = None, limite: Optional[int] = None) -> str:
    """consultarAdministradora - GET /INTEGRACAO/ADMINISTRADORA"""
    params = {}
    if administradora_codigo is not None:
        params["administradoraCodigo"] = administradora_codigo
    if empresa_codigo is not None:
        params["empresaCodigo"] = empresa_codigo
    if administradora_codigo_externo is not None:
        params["administradoraCodigoExterno"] = administradora_codigo_externo
    if ultimo_codigo is not None:
        params["ultimoCodigo"] = ultimo_codigo
    if limite is not None:
        params["limite"] = limite
    result = client.get("/INTEGRACAO/ADMINISTRADORA", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_adiantamento_fornecedor(data_inicial: str, data_final: str, fornecedor_codigo: Optional[int] = None, empresa_codigo: Optional[int] = None, tipo_adiantamento: Optional[str] = None, ultimo_codigo: Optional[int] = None, limite: Optional[int] = None) -> str:
    """consultarAdiantamentoFornecedor - GET /INTEGRACAO/ADIANTAMENTO_FORNECEDOR"""
    params = {}
    if fornecedor_codigo is not None:
        params["fornecedorCodigo"] = fornecedor_codigo
    if empresa_codigo is not None:
        params["empresaCodigo"] = empresa_codigo
    if tipo_adiantamento is not None:
        params["tipoAdiantamento"] = tipo_adiantamento
    if data_inicial is not None:
        params["dataInicial"] = data_inicial
    if data_final is not None:
        params["dataFinal"] = data_final
    if ultimo_codigo is not None:
        params["ultimoCodigo"] = ultimo_codigo
    if limite is not None:
        params["limite"] = limite
    result = client.get("/INTEGRACAO/ADIANTAMENTO_FORNECEDOR", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_abastecimento(data_inicial: str, data_final: str, tipo_data: Optional[str] = None, ultimo_codigo: Optional[int] = None, limite: Optional[int] = None) -> str:
    """consultarAbastecimento - GET /INTEGRACAO/ABASTECIMENTO"""
    params = {}
    if data_inicial is not None:
        params["dataInicial"] = data_inicial
    if data_final is not None:
        params["dataFinal"] = data_final
    if tipo_data is not None:
        params["tipoData"] = tipo_data
    if ultimo_codigo is not None:
        params["ultimoCodigo"] = ultimo_codigo
    if limite is not None:
        params["limite"] = limite
    result = client.get("/INTEGRACAO/ABASTECIMENTO", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def excluir_titulo(id: str) -> str:
    """excluirTitulo - DELETE /INTEGRACAO/TITULO_PAGAR/{id}"""
    endpoint = f"/INTEGRACAO/TITULO_PAGAR/{id}"
    params = {}

    result = client.delete(endpoint, params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return "Registro excluído com sucesso."


@mcp.tool()
def excluir_prazo_tabela_preco_item(id: str) -> str:
    """excluirPrazoTabelaPrecoItem - DELETE /INTEGRACAO/PRAZO_TABELA_PRECO_ITEM/{id}"""
    endpoint = f"/INTEGRACAO/PRAZO_TABELA_PRECO_ITEM/{id}"
    params = {}

    result = client.delete(endpoint, params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return "Registro excluído com sucesso."


# =============================================================================
# FERRAMENTAS - INTEGRAÇÃO PEDIDO COMBUSTÍVEL
# =============================================================================


@mcp.tool()
def receber_titulo_cartao(id: str, dados: Dict[str, Any]) -> str:
    """receberTituloCartao - PUT /INTEGRACAO/PEDIDO_COMBUSTIVEL/PEDIDO/{id}/RECEBER_TITULO_EM_CARTAO"""
    endpoint = f"/INTEGRACAO/PEDIDO_COMBUSTIVEL/PEDIDO/{id}/RECEBER_TITULO_EM_CARTAO"
    params = {}

    result = client.put(endpoint, data=dados, params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return f"Operação realizada com sucesso.\n{format_response(result.get('data', {}))}"


@mcp.tool()
def incluir_pedido(dados: Dict[str, Any]) -> str:
    """incluirPedido - POST /INTEGRACAO/PEDIDO_COMBUSTIVEL/PEDIDO"""
    params = {}

    result = client.post("/INTEGRACAO/PEDIDO_COMBUSTIVEL/PEDIDO", data=dados, params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return f"Operação realizada com sucesso.\n{format_response(result.get('data', {}))}"


@mcp.tool()
def pedido_faturar(id: str, dados: Dict[str, Any]) -> str:
    """pedidoFaturar - POST /INTEGRACAO/PEDIDO_COMBUSTIVEL/PEDIDO/{id}/FATURAR"""
    params = {}

    result = client.post("/INTEGRACAO/PEDIDO_COMBUSTIVEL/PEDIDO/{id}/FATURAR", data=dados, params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return f"Operação realizada com sucesso.\n{format_response(result.get('data', {}))}"


@mcp.tool()
def pedido_danfe(id: str) -> str:
    """pedidoDanfe - POST /INTEGRACAO/PEDIDO_COMBUSTIVEL/PEDIDO/{id}/DANFE"""
    params = {}

    result = client.post("/INTEGRACAO/PEDIDO_COMBUSTIVEL/PEDIDO/{id}/DANFE", data=dados, params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return f"Operação realizada com sucesso.\n{format_response(result.get('data', {}))}"


@mcp.tool()
def cliente_consultar(cnpj_cpf: str) -> str:
    """clienteConsultar - GET /INTEGRACAO/PEDIDO_COMBUSTIVEL/CLIENTE"""
    params = {}
    if cnpj_cpf is not None:
        params["cnpjCpf"] = cnpj_cpf
    result = client.get("/INTEGRACAO/PEDIDO_COMBUSTIVEL/CLIENTE", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_produto_combustivel() -> str:
    """consultarProdutoCombustivel - GET /INTEGRACAO/PEDIDO_COMBUSTIVEL/PRODUTO"""
    params = {}

    result = client.get("/INTEGRACAO/PEDIDO_COMBUSTIVEL/PRODUTO", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_pedido(id: str) -> str:
    """consultarPedido - GET /INTEGRACAO/PEDIDO_COMBUSTIVEL/PEDIDO/{id}"""
    params = {}

    result = client.get("/INTEGRACAO/PEDIDO_COMBUSTIVEL/PEDIDO/{id}", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def excluir_pedido(id: str) -> str:
    """excluirPedido - DELETE /INTEGRACAO/PEDIDO_COMBUSTIVEL/PEDIDO/{id}"""
    endpoint = f"/INTEGRACAO/PEDIDO_COMBUSTIVEL/PEDIDO/{id}"
    params = {}

    result = client.delete(endpoint, params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return "Registro excluído com sucesso."


@mcp.tool()
def pedido_xml(id: str) -> str:
    """pedidoXml - GET /INTEGRACAO/PEDIDO_COMBUSTIVEL/PEDIDO/{id}/XML"""
    params = {}

    result = client.get("/INTEGRACAO/PEDIDO_COMBUSTIVEL/PEDIDO/{id}/XML", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def pedido_status(pedidos: Optional[list] = None) -> str:
    """pedidoStatus - GET /INTEGRACAO/PEDIDO_COMBUSTIVEL/PEDIDO/STATUS"""
    params = {}
    if pedidos is not None:
        params["pedidos"] = pedidos
    result = client.get("/INTEGRACAO/PEDIDO_COMBUSTIVEL/PEDIDO/STATUS", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


# =============================================================================
# FERRAMENTAS - INTEGRAÇÃO RELATÓRIOS
# =============================================================================


@mcp.tool()
def vendas_periodo(cupom_cancelado: bool, ordenacao_por: str, data_inicial: str, data_final: str, tipo_data: str, agrupamento_por: Optional[str] = None, prazo: Optional[list] = None, turno: Optional[list] = None, hora_acompanha_data: Optional[bool] = None, hora_inicial: Optional[str] = None, hora_final: Optional[str] = None, grupo_produto: Optional[list] = None, ecf: Optional[list] = None, funcionario: Optional[list] = None, produto: Optional[list] = None, cliente: Optional[int] = None, pdv_caixa: Optional[list] = None, tipo_produto: Optional[list] = None, filial: Optional[list] = None, estoque: Optional[list] = None, tipo_venda: Optional[str] = None, apresenta_preco_medio: Optional[bool] = None, grupo_cliente: Optional[list] = None, consolidar: Optional[bool] = None, sub_grupo_produto_nivel1: Optional[list] = None, sub_grupo_produto_nivel2: Optional[list] = None, sub_grupo_produto_nivel3: Optional[list] = None, agrupar_totalizadores: Optional[str] = None, depto_selcon: Optional[str] = None, pdv_gerou_venda: Optional[list] = None, centro_custo: Optional[list] = None) -> str:
    """vendasPeriodo - GET /INTEGRACAO/RELATORIO/VENDA_PERIODO"""
    params = {}
    if cupom_cancelado is not None:
        params["cupomCancelado"] = cupom_cancelado
    if ordenacao_por is not None:
        params["ordenacaoPor"] = ordenacao_por
    if agrupamento_por is not None:
        params["agrupamentoPor"] = agrupamento_por
    if prazo is not None:
        params["prazo"] = prazo
    if turno is not None:
        params["turno"] = turno
    if hora_acompanha_data is not None:
        params["horaAcompanhaData"] = hora_acompanha_data
    if data_inicial is not None:
        params["dataInicial"] = data_inicial
    if data_final is not None:
        params["dataFinal"] = data_final
    if hora_inicial is not None:
        params["horaInicial"] = hora_inicial
    if hora_final is not None:
        params["horaFinal"] = hora_final
    if grupo_produto is not None:
        params["grupoProduto"] = grupo_produto
    if ecf is not None:
        params["ecf"] = ecf
    if funcionario is not None:
        params["funcionario"] = funcionario
    if produto is not None:
        params["produto"] = produto
    if cliente is not None:
        params["cliente"] = cliente
    if pdv_caixa is not None:
        params["pdvCaixa"] = pdv_caixa
    if tipo_produto is not None:
        params["tipoProduto"] = tipo_produto
    if filial is not None:
        params["filial"] = filial
    if estoque is not None:
        params["estoque"] = estoque
    if tipo_venda is not None:
        params["tipoVenda"] = tipo_venda
    if tipo_data is not None:
        params["tipoData"] = tipo_data
    if apresenta_preco_medio is not None:
        params["apresentaPrecoMedio"] = apresenta_preco_medio
    if grupo_cliente is not None:
        params["grupoCliente"] = grupo_cliente
    if consolidar is not None:
        params["consolidar"] = consolidar
    if sub_grupo_produto_nivel1 is not None:
        params["subGrupoProdutoNivel1"] = sub_grupo_produto_nivel1
    if sub_grupo_produto_nivel2 is not None:
        params["subGrupoProdutoNivel2"] = sub_grupo_produto_nivel2
    if sub_grupo_produto_nivel3 is not None:
        params["subGrupoProdutoNivel3"] = sub_grupo_produto_nivel3
    if agrupar_totalizadores is not None:
        params["agruparTotalizadores"] = agrupar_totalizadores
    if depto_selcon is not None:
        params["deptoSelcon"] = depto_selcon
    if pdv_gerou_venda is not None:
        params["pdvGerouVenda"] = pdv_gerou_venda
    if centro_custo is not None:
        params["centroCusto"] = centro_custo
    result = client.get("/INTEGRACAO/RELATORIO/VENDA_PERIODO", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def relatorio_personalizado(relatorio_codigo: str, cliente: Optional[list] = None, data_inicial: Optional[str] = None, data_final: Optional[str] = None, caixa: Optional[int] = None, funcionario: Optional[list] = None, grupo_produto: Optional[list] = None, administradora: Optional[list] = None, situacao_receber: Optional[str] = None, filial: Optional[list] = None, produto: Optional[list] = None, distribuidora: Optional[str] = None, modelo_documento_fiscal: Optional[list] = None, plano_conta: Optional[int] = None, intermediador: Optional[list] = None, data_posicao: Optional[str] = None, nota: Optional[str] = None, situacao_trr: Optional[list] = None, sub_grupo_produto: Optional[list] = None, estoque: Optional[list] = None, centro_custo: Optional[list] = None, fidelidade: Optional[int] = None, tipo_premiacao: Optional[str] = None, situacao_caixa: Optional[str] = None, filial_origem: Optional[int] = None, tipo_reajuste: Optional[list] = None, saldo_inicial: Optional[float] = None, placa: Optional[str] = None, cupom: Optional[str] = None, fornecedor: Optional[list] = None, titulo: Optional[str] = None, remessa: Optional[str] = None, conta: Optional[list] = None, grupo_cliente: Optional[list] = None, motorista: Optional[list] = None, veiculo: Optional[list] = None, prazo: Optional[list] = None, centro_custo_cliente: Optional[list] = None, cfop: Optional[list] = None, tipo_filtro: Optional[str] = None, tipo_operacao: Optional[str] = None, valor1_comparador: Optional[float] = None, valor2_comparador: Optional[float] = None) -> str:
    """relatorioPersonalizado - GET /INTEGRACAO/RELATORIO/RELATORIO_PERSONALIZADO/{relatorioCodigo}"""
    params = {}
    if cliente is not None:
        params["cliente"] = cliente
    if data_inicial is not None:
        params["dataInicial"] = data_inicial
    if data_final is not None:
        params["dataFinal"] = data_final
    if caixa is not None:
        params["caixa"] = caixa
    if funcionario is not None:
        params["funcionario"] = funcionario
    if grupo_produto is not None:
        params["grupoProduto"] = grupo_produto
    if administradora is not None:
        params["administradora"] = administradora
    if situacao_receber is not None:
        params["situacaoReceber"] = situacao_receber
    if filial is not None:
        params["filial"] = filial
    if produto is not None:
        params["produto"] = produto
    if distribuidora is not None:
        params["distribuidora"] = distribuidora
    if modelo_documento_fiscal is not None:
        params["modeloDocumentoFiscal"] = modelo_documento_fiscal
    if plano_conta is not None:
        params["planoConta"] = plano_conta
    if intermediador is not None:
        params["intermediador"] = intermediador
    if data_posicao is not None:
        params["dataPosicao"] = data_posicao
    if nota is not None:
        params["nota"] = nota
    if situacao_trr is not None:
        params["situacaoTrr"] = situacao_trr
    if sub_grupo_produto is not None:
        params["subGrupoProduto"] = sub_grupo_produto
    if estoque is not None:
        params["estoque"] = estoque
    if centro_custo is not None:
        params["centroCusto"] = centro_custo
    if fidelidade is not None:
        params["fidelidade"] = fidelidade
    if tipo_premiacao is not None:
        params["tipoPremiacao"] = tipo_premiacao
    if situacao_caixa is not None:
        params["situacaoCaixa"] = situacao_caixa
    if filial_origem is not None:
        params["filialOrigem"] = filial_origem
    if tipo_reajuste is not None:
        params["tipoReajuste"] = tipo_reajuste
    if saldo_inicial is not None:
        params["saldoInicial"] = saldo_inicial
    if placa is not None:
        params["placa"] = placa
    if cupom is not None:
        params["cupom"] = cupom
    if fornecedor is not None:
        params["fornecedor"] = fornecedor
    if titulo is not None:
        params["titulo"] = titulo
    if remessa is not None:
        params["remessa"] = remessa
    if conta is not None:
        params["conta"] = conta
    if grupo_cliente is not None:
        params["grupoCliente"] = grupo_cliente
    if motorista is not None:
        params["motorista"] = motorista
    if veiculo is not None:
        params["veiculo"] = veiculo
    if prazo is not None:
        params["prazo"] = prazo
    if centro_custo_cliente is not None:
        params["centroCustoCliente"] = centro_custo_cliente
    if cfop is not None:
        params["cfop"] = cfop
    if tipo_filtro is not None:
        params["tipoFiltro"] = tipo_filtro
    if tipo_operacao is not None:
        params["tipoOperacao"] = tipo_operacao
    if valor1_comparador is not None:
        params["valor1Comparador"] = valor1_comparador
    if valor2_comparador is not None:
        params["valor2Comparador"] = valor2_comparador
    result = client.get("/INTEGRACAO/RELATORIO/RELATORIO_PERSONALIZADO/{relatorioCodigo}", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def produtividade_funcionario(tipo_relatorio: str, tipo_data: Optional[str] = None, funcionario: Optional[int] = None, produto: Optional[int] = None, caixa: Optional[list] = None, data_inicial: Optional[str] = None, data_final: Optional[str] = None, ordenacao: Optional[str] = None, referencia_funcionario: Optional[str] = None, grupo_produto: Optional[list] = None, sub_grupo_produto: Optional[list] = None, pdv: Optional[list] = None, funcoes: Optional[list] = None, tipo_filtro: Optional[str] = None, intervalo_filtro: Optional[str] = None, valor_inicial_filtro: Optional[float] = None, valor_final_filtro: Optional[float] = None, calculo_ticket_medio: Optional[str] = None, agrupamento: Optional[str] = None, filial: Optional[list] = None, comissao: Optional[str] = None, detalha_totalizador_por_grupo: Optional[bool] = None, cliente: Optional[list] = None, grupo_cliente: Optional[list] = None) -> str:
    """produtividadeFuncionario - GET /INTEGRACAO/RELATORIO/PRODUTIVIDADE_FUNCIONARIO"""
    params = {}
    if tipo_relatorio is not None:
        params["tipoRelatorio"] = tipo_relatorio
    if tipo_data is not None:
        params["tipoData"] = tipo_data
    if funcionario is not None:
        params["funcionario"] = funcionario
    if produto is not None:
        params["produto"] = produto
    if caixa is not None:
        params["caixa"] = caixa
    if data_inicial is not None:
        params["dataInicial"] = data_inicial
    if data_final is not None:
        params["dataFinal"] = data_final
    if ordenacao is not None:
        params["ordenacao"] = ordenacao
    if referencia_funcionario is not None:
        params["referenciaFuncionario"] = referencia_funcionario
    if grupo_produto is not None:
        params["grupoProduto"] = grupo_produto
    if sub_grupo_produto is not None:
        params["subGrupoProduto"] = sub_grupo_produto
    if pdv is not None:
        params["pdv"] = pdv
    if funcoes is not None:
        params["funcoes"] = funcoes
    if tipo_filtro is not None:
        params["tipoFiltro"] = tipo_filtro
    if intervalo_filtro is not None:
        params["intervaloFiltro"] = intervalo_filtro
    if valor_inicial_filtro is not None:
        params["valorInicialFiltro"] = valor_inicial_filtro
    if valor_final_filtro is not None:
        params["valorFinalFiltro"] = valor_final_filtro
    if calculo_ticket_medio is not None:
        params["calculoTicketMedio"] = calculo_ticket_medio
    if agrupamento is not None:
        params["agrupamento"] = agrupamento
    if filial is not None:
        params["filial"] = filial
    if comissao is not None:
        params["comissao"] = comissao
    if detalha_totalizador_por_grupo is not None:
        params["detalhaTotalizadorPorGrupo"] = detalha_totalizador_por_grupo
    if cliente is not None:
        params["cliente"] = cliente
    if grupo_cliente is not None:
        params["grupoCliente"] = grupo_cliente
    result = client.get("/INTEGRACAO/RELATORIO/PRODUTIVIDADE_FUNCIONARIO", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def mapa_desempenho(data_inicial: str, data_final: str, funcionario: Optional[list] = None, grupo_produto: Optional[list] = None, sub_grupo_produto: Optional[list] = None, produto: Optional[int] = None, usa_dado_premiacao: Optional[bool] = None, base_comissao: Optional[str] = None, referencia_funcionario: Optional[str] = None, tipo_relatorio: Optional[str] = None, ordenacao: Optional[str] = None, pdv: Optional[list] = None, premiacao_baseada_historico: Optional[bool] = None, apenas_comissionado: Optional[bool] = None, hora_inicial: Optional[str] = None, hora_final: Optional[str] = None, cliente: Optional[int] = None, apuracao: Optional[str] = None, filial: Optional[list] = None) -> str:
    """mapaDesempenho - GET /INTEGRACAO/RELATORIO/MAPA_DESEMPENHO"""
    params = {}
    if data_inicial is not None:
        params["dataInicial"] = data_inicial
    if data_final is not None:
        params["dataFinal"] = data_final
    if funcionario is not None:
        params["funcionario"] = funcionario
    if grupo_produto is not None:
        params["grupoProduto"] = grupo_produto
    if sub_grupo_produto is not None:
        params["subGrupoProduto"] = sub_grupo_produto
    if produto is not None:
        params["produto"] = produto
    if usa_dado_premiacao is not None:
        params["usaDadoPremiacao"] = usa_dado_premiacao
    if base_comissao is not None:
        params["baseComissao"] = base_comissao
    if referencia_funcionario is not None:
        params["referenciaFuncionario"] = referencia_funcionario
    if tipo_relatorio is not None:
        params["tipoRelatorio"] = tipo_relatorio
    if ordenacao is not None:
        params["ordenacao"] = ordenacao
    if pdv is not None:
        params["pdv"] = pdv
    if premiacao_baseada_historico is not None:
        params["premiacaoBaseadaHistorico"] = premiacao_baseada_historico
    if apenas_comissionado is not None:
        params["apenasComissionado"] = apenas_comissionado
    if hora_inicial is not None:
        params["horaInicial"] = hora_inicial
    if hora_final is not None:
        params["horaFinal"] = hora_final
    if cliente is not None:
        params["cliente"] = cliente
    if apuracao is not None:
        params["apuracao"] = apuracao
    if filial is not None:
        params["filial"] = filial
    result = client.get("/INTEGRACAO/RELATORIO/MAPA_DESEMPENHO", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


# =============================================================================
# PONTO DE ENTRADA
# =============================================================================

def main():
    """Ponto de entrada principal do servidor MCP."""
    if not API_KEY:
        logger.error("=" * 60)
        logger.error("ERRO: WEBPOSTO_API_KEY não configurada!")
        logger.error("Defina a variável de ambiente WEBPOSTO_API_KEY")
        logger.error("=" * 60)
        sys.exit(1)
    
    logger.info("=" * 60)
    logger.info("WebPosto MCP Server - Quality Automação v1.2.0")
    logger.info("=" * 60)
    logger.info(f"URL Base: {WEBPOSTO_BASE_URL}")
    logger.info(f"Chave API: {'*' * 8}...{API_KEY[-8:] if len(API_KEY) > 8 else '****'}")
    logger.info("=" * 60)
    
    mcp.run()

if __name__ == "__main__":
    main()
