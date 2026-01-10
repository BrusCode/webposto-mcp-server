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

# Compatibilidade com FastMCP Cloud (pacote fastmcp) e MCP SDK (pacote mcp)
try:
    from fastmcp import FastMCP
except ImportError:
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
        """Adiciona o parâmetro de autenticação 'chave' aos parâmetros da requisição.
        
        A chave é lida dinamicamente do ambiente para garantir que
        variáveis definidas após a importação do módulo sejam capturadas.
        """
        if params is None:
            params = {}
        # Ler a chave dinamicamente do ambiente
        api_key = os.getenv('WEBPOSTO_API_KEY', '') or API_KEY
        if api_key:
            params['chave'] = api_key
        else:
            logger.warning("AVISO: Requisição sem chave de API - WEBPOSTO_API_KEY não configurada")
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
            # Log da URL com parâmetros (sem expor a chave completa)
            params_log = {k: (v[:8] + '...' if k == 'chave' and v else v) for k, v in params.items()}
            logger.info(f"Requisição {method} para: {url}")
            logger.debug(f"Parâmetros: {params_log}")
            
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
    """
    **Registra o recebimento de um título a receber.**

    Esta tool permite baixar/quitar um título a receber, registrando o pagamento efetivo
    do cliente. É essencial para gestão de contas a receber e fluxo de caixa.

    **Quando usar:**
    - Para registrar recebimento de duplicatas
    - Para baixar títulos após confirmação de pagamento
    - Para conciliação bancária
    - Para atualização de saldo de clientes

    **Fluxo de Uso Essencial:**
    1. **Consulte o Título:** Use `consultar_titulo_receber` para obter o código do título.
    2. **Registre o Recebimento:** Chame `receber_titulo` com os dados do recebimento.

    **Parâmetros (via objeto `dados`):**
    - `tituloCodigo` (int, obrigatório): Código do título a receber.
      Obter via: `consultar_titulo_receber`
    - `dataRecebimento` (str, obrigatório): Data do recebimento (YYYY-MM-DD).
    - `valorRecebido` (float, obrigatório): Valor efetivamente recebido.
    - `formaPagamento` (str, obrigatório): Forma de pagamento.
      Valores: "D" (Dinheiro), "C" (Cheque), "T" (Transferência), "P" (PIX),
      "CC" (Cartão Crédito), "CD" (Cartão Débito)
    - `contaBancariaCodigo` (int, opcional): Código da conta bancária de destino.
    - `observacao` (str, opcional): Observações sobre o recebimento.

    **Exemplo de Uso (Python):**
    ```python
    # Cenário 1: Receber título em dinheiro
    resultado = receber_titulo(
        dados={
            "tituloCodigo": 12345,
            "dataRecebimento": "2025-01-10",
            "valorRecebido": 1500.50,
            "formaPagamento": "D"  # Dinheiro
        }
    )

    # Cenário 2: Receber título via PIX
    resultado = receber_titulo(
        dados={
            "tituloCodigo": 12346,
            "dataRecebimento": "2025-01-10",
            "valorRecebido": 2500.00,
            "formaPagamento": "P",  # PIX
            "contaBancariaCodigo": 1,
            "observacao": "Recebido via PIX - Comprovante #123"
        }
    )
    ```

    **Dependências:**
    - Requer: `consultar_titulo_receber` (para obter tituloCodigo)

    **Tools Relacionadas:**
    - `consultar_titulo_receber` - Consultar títulos para receber
    - `receber_cheque` - Receber especificamente cheques
    - `receber_cartoes` - Receber especificamente cartões
    """
    endpoint = f"/INTEGRACAO/RECEBER_TITULO"
    params = {}

    result = client.put(endpoint, data=dados, params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return f"Operação realizada com sucesso.\n{format_response(result.get('data', {}))}"


@mcp.tool()
def receber_cheque(dados: Dict[str, Any], empresa_codigo: Optional[int] = None) -> str:
    """
    **Registra o recebimento de cheque.**

    Esta tool permite registrar o recebimento de pagamentos via cheque, incluindo
    cheques pré-datados. É específica para controle de cheques recebidos.

    **Quando usar:**
    - Para registrar recebimento de cheques
    - Para controle de cheques pré-datados
    - Para conciliação bancária de cheques

    **Fluxo de Uso Essencial:**
    1. **Consulte o Título:** Use `consultar_titulo_receber` para obter informações.
    2. **Registre o Cheque:** Chame `receber_cheque` com os dados do cheque.

    **Parâmetros:**
    - `dados` (Dict, obrigatório): Objeto com dados do cheque:
      * `tituloCodigo` (int): Código do título
      * `dataRecebimento` (str): Data do recebimento (YYYY-MM-DD)
      * `valorRecebido` (float): Valor do cheque
      * `numeroCheque` (str): Número do cheque
      * `banco` (str): Código do banco
      * `agencia` (str): Número da agência
      * `conta` (str): Número da conta
      * `dataBomPara` (str, opcional): Data de bom para (cheque pré-datado)
    - `empresa_codigo` (int, opcional): Código da empresa.

    **Exemplo de Uso (Python):**
    ```python
    # Cenário 1: Receber cheque à vista
    resultado = receber_cheque(
        dados={
            "tituloCodigo": 12345,
            "dataRecebimento": "2025-01-10",
            "valorRecebido": 1500.00,
            "numeroCheque": "000123",
            "banco": "001",  # Banco do Brasil
            "agencia": "1234",
            "conta": "56789-0"
        },
        empresa_codigo=7
    )

    # Cenário 2: Receber cheque pré-datado
    resultado = receber_cheque(
        dados={
            "tituloCodigo": 12346,
            "dataRecebimento": "2025-01-10",
            "valorRecebido": 2500.00,
            "numeroCheque": "000124",
            "banco": "237",  # Bradesco
            "agencia": "5678",
            "conta": "12345-6",
            "dataBomPara": "2025-02-10"  # Pré-datado para 10/02
        },
        empresa_codigo=7
    )
    ```

    **Dependências:**
    - Requer: `consultar_titulo_receber` (para obter tituloCodigo)

    **Tools Relacionadas:**
    - `receber_titulo` - Receber títulos em geral
    - `consultar_titulo_receber` - Consultar títulos
    """
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
    """
    **Registra o recebimento via cartão de crédito/débito.**

    Esta tool permite registrar o recebimento de pagamentos via cartão, incluindo
    informações da administradora e autorização.

    **Quando usar:**
    - Para registrar recebimentos via cartão
    - Para controle de transações com administradoras
    - Para conciliação de recebíveis de cartões

    **Fluxo de Uso Essencial:**
    1. **Consulte o Título:** Use `consultar_titulo_receber` para obter informações.
    2. **Registre o Cartão:** Chame `receber_cartoes` com os dados da transação.

    **Parâmetros (via objeto `dados`):**
    - `tituloCodigo` (int, obrigatório): Código do título a receber.
    - `dataRecebimento` (str, obrigatório): Data do recebimento (YYYY-MM-DD).
    - `valorRecebido` (float, obrigatório): Valor da transação.
    - `tipoCartao` (str, obrigatório): Tipo do cartão.
      Valores: "CC" (Crédito), "CD" (Débito)
    - `administradoraCodigo` (int, obrigatório): Código da administradora.
    - `numeroAutorizacao` (str, opcional): Número de autorização da transação.
    - `numeroParcelas` (int, opcional): Número de parcelas (para crédito).
    - `nsu` (str, opcional): NSU da transação.

    **Exemplo de Uso (Python):**
    ```python
    # Cenário 1: Receber via cartão de débito
    resultado = receber_cartoes(
        dados={
            "tituloCodigo": 12345,
            "dataRecebimento": "2025-01-10",
            "valorRecebido": 1500.00,
            "tipoCartao": "CD",  # Débito
            "administradoraCodigo": 1,  # Ex: Cielo
            "numeroAutorizacao": "123456",
            "nsu": "789012"
        }
    )

    # Cenário 2: Receber via cartão de crédito parcelado
    resultado = receber_cartoes(
        dados={
            "tituloCodigo": 12346,
            "dataRecebimento": "2025-01-10",
            "valorRecebido": 3000.00,
            "tipoCartao": "CC",  # Crédito
            "administradoraCodigo": 2,  # Ex: Rede
            "numeroAutorizacao": "654321",
            "numeroParcelas": 3,  # 3x sem juros
            "nsu": "345678"
        }
    )
    ```

    **Dependências:**
    - Requer: `consultar_titulo_receber` (para obter tituloCodigo)

    **Tools Relacionadas:**
    - `receber_titulo` - Receber títulos em geral
    - `consultar_titulo_receber` - Consultar títulos

    **Dica:**
    Para cartões de crédito parcelados, o sistema pode gerar múltiplos títulos
    a receber (um por parcela) automaticamente.
    """
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
    """
    **Consulta títulos a receber (contas a receber).**

    Esta tool retorna títulos financeiros a receber, como duplicatas, cheques pré-datados,
    cartões a receber, etc. É essencial para gestão de contas a receber e fluxo de caixa.

    **Quando usar:**
    - Para listar títulos pendentes de recebimento
    - Para acompanhamento de inadimplência
    - Para relatórios de contas a receber
    - Para conciliação financeira

    **Fluxo de Uso Essencial:**
    1. **Obtenha o ID da Empresa (Opcional):** Use `consultar_empresas` para filtrar.
    2. **Execute a Consulta:** Chame `consultar_titulo_receber` com período e filtros.

    **Parâmetros Principais:**
    - `data_inicial` (str, obrigatório): Data de início no formato YYYY-MM-DD.
      Exemplo: "2025-01-10"
    - `data_final` (str, obrigatório): Data de fim no formato YYYY-MM-DD.
      Exemplo: "2025-01-10"
    - `empresa_codigo` (int, opcional): Código da empresa/filial.
      Obter via: `consultar_empresas`
      Exemplo: 7
    - `apenas_pendente` (bool, opcional): Se True, retorna apenas títulos não recebidos.
      Muito útil para gestão de inadimplência.
      Exemplo: True
    - `data_filtro` (str, opcional): Tipo de data para filtro.
      Valores: "VENCIMENTO", "EMISSAO", "RECEBIMENTO"
      Default: "VENCIMENTO"
    - `venda_codigo` (List[int], opcional): Filtrar por vendas específicas.
      Obter via: `consultar_venda`
    - `convertido` (bool, opcional): Filtrar títulos convertidos.
    - `codigo_duplicata` (int, opcional): Código de duplicata específica.
    - `limite` (int, opcional): Número máximo de registros (default: 100, max: 2000).
    - `ultimo_codigo` (int, opcional): Para paginação.

    **Retorno:**
    Lista de títulos a receber contendo:
    - Código do título
    - Número da duplicata
    - Cliente
    - Valor original
    - Valor recebido
    - Saldo pendente
    - Data de emissão
    - Data de vencimento
    - Data de recebimento (se recebido)
    - Situação (pendente/recebido/cancelado)
    - Empresa/filial

    **Exemplo de Uso (Python):**
    ```python
    # Cenário 1: Listar títulos pendentes (inadimplência)
    pendentes = consultar_titulo_receber(
        data_inicial="2025-01-01",
        data_final="2025-01-10",
        empresa_codigo=7,
        apenas_pendente=True,
        data_filtro="VENCIMENTO"
    )

    # Cenário 2: Listar todos os títulos do mês
    titulos = consultar_titulo_receber(
        data_inicial="2025-01-01",
        data_final="2025-01-31",
        empresa_codigo=7
    )

    # Cenário 3: Relatório de inadimplência
    import datetime
    hoje = datetime.date.today()
    vencidos = consultar_titulo_receber(
        data_inicial="2024-01-01",
        data_final=hoje.strftime("%Y-%m-%d"),
        empresa_codigo=7,
        apenas_pendente=True,
        data_filtro="VENCIMENTO"
    )
    
    total_vencido = sum(t["saldoPendente"] for t in vencidos)
    print(f"Total vencido: R$ {total_vencido:,.2f}")
    ```

    **Dependências:**
    - Opcional: `consultar_empresas` (para obter empresa_codigo)
    - Opcional: `consultar_venda` (para obter venda_codigo)

    **Tools Relacionadas:**
    - `receber_titulo` - Registrar recebimento de título
    - `incluir_titulo_receber` - Criar novo título a receber
    - `consultar_venda` - Consultar vendas que geraram títulos

    **Dica:**
    Use `apenas_pendente=True` com `data_filtro="VENCIMENTO"` para relatórios de
    inadimplência e cobrança.
    """
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
    """
    **Cria um novo título a receber.**

    Esta tool permite criar manualmente um título a receber (duplicata, cheque, etc.)
    no sistema. É útil para lançamentos manuais ou integrações externas.

    **Quando usar:**
    - Para criar títulos de vendas externas
    - Para lançamentos manuais de contas a receber
    - Para integrações com outros sistemas

    **Fluxo de Uso Essencial:**
    1. **Prepare os Dados:** Monte o objeto com informações do título.
    2. **Crie o Título:** Chame `incluir_titulo_receber` com os dados.

    **Parâmetros (via objeto `dados`):**
    - `clienteCodigo` (int, obrigatório): Código do cliente.
      Obter via: `consultar_cliente`
    - `valorOriginal` (float, obrigatório): Valor do título.
    - `dataEmissao` (str, obrigatório): Data de emissão (YYYY-MM-DD).
    - `dataVencimento` (str, obrigatório): Data de vencimento (YYYY-MM-DD).
    - `numeroDuplicata` (str, opcional): Número da duplicata.
    - `observacao` (str, opcional): Observações.
    - `empresaCodigo` (int, opcional): Código da empresa.

    **Exemplo de Uso (Python):**
    ```python
    # Criar título a receber
    resultado = incluir_titulo_receber(
        dados={
            "clienteCodigo": 123,
            "valorOriginal": 1500.00,
            "dataEmissao": "2025-01-10",
            "dataVencimento": "2025-02-10",
            "numeroDuplicata": "DUP-001",
            "observacao": "Venda externa - Pedido #456",
            "empresaCodigo": 7
        }
    )
    ```

    **Dependências:**
    - Requer: `consultar_cliente` (para obter clienteCodigo)
    - Opcional: `consultar_empresas` (para obter empresaCodigo)

    **Tools Relacionadas:**
    - `consultar_titulo_receber` - Consultar títulos criados
    - `receber_titulo` - Registrar recebimento
    """
    params = {}

    result = client.post("/INTEGRACAO/TITULO_RECEBER", data=dados, params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return f"Operação realizada com sucesso.\n{format_response(result.get('data', {}))}"


@mcp.tool()
def consultar_titulo_pagar(data_inicial: Optional[str] = None, data_final: Optional[str] = None, data_hora_atualizacao: Optional[str] = None, apenas_pendente: Optional[bool] = None, data_filtro: Optional[str] = None, ultimo_codigo: Optional[int] = None, limite: Optional[int] = None, empresa_codigo: Optional[int] = None, nota_entrada_codigo: Optional[int] = None, titulo_pagar_codigo: Optional[int] = None, fornecedor_codigo: Optional[int] = None, linha_digitavel: Optional[str] = None, autorizado: Optional[bool] = None, tipo_lancamento: Optional[str] = None) -> str:
    """
    **Consulta títulos a pagar (contas a pagar).**

    Esta tool retorna títulos financeiros a pagar, como boletos de fornecedores, notas
    fiscais a pagar, despesas operacionais, etc. É essencial para gestão de contas a
    pagar e fluxo de caixa.

    **Quando usar:**
    - Para listar títulos pendentes de pagamento
    - Para planejamento de fluxo de caixa
    - Para relatórios de contas a pagar
    - Para conciliação financeira com fornecedores

    **Fluxo de Uso Essencial:**
    1. **Obtenha o ID da Empresa (Opcional):** Use `consultar_empresas` para filtrar.
    2. **Execute a Consulta:** Chame `consultar_titulo_pagar` com período e filtros.

    **Parâmetros Principais:**
    - `data_inicial` (str, opcional): Data de início no formato YYYY-MM-DD.
      Exemplo: "2025-01-10"
    - `data_final` (str, opcional): Data de fim no formato YYYY-MM-DD.
      Exemplo: "2025-01-10"
    - `empresa_codigo` (int, opcional): Código da empresa/filial.
      Obter via: `consultar_empresas`
      Exemplo: 7
    - `apenas_pendente` (bool, opcional): Se True, retorna apenas títulos não pagos.
      Muito útil para gestão de contas a pagar.
      Exemplo: True
    - `data_filtro` (str, opcional): Tipo de data para filtro.
      Valores: "VENCIMENTO", "EMISSAO", "PAGAMENTO"
      Default: "VENCIMENTO"
    - `fornecedor_codigo` (int, opcional): Filtrar por fornecedor específico.
      Obter via: `consultar_fornecedor`
    - `nota_entrada_codigo` (int, opcional): Filtrar por nota fiscal de entrada.
    - `linha_digitavel` (str, opcional): Buscar por linha digitável de boleto.
    - `autorizado` (bool, opcional): Filtrar títulos autorizados para pagamento.
    - `tipo_lancamento` (str, opcional): Tipo de lançamento.
    - `limite` (int, opcional): Número máximo de registros (default: 100, max: 2000).
    - `ultimo_codigo` (int, opcional): Para paginação.

    **Retorno:**
    Lista de títulos a pagar contendo:
    - Código do título
    - Número do documento
    - Fornecedor
    - Valor original
    - Valor pago
    - Saldo pendente
    - Data de emissão
    - Data de vencimento
    - Data de pagamento (se pago)
    - Situação (pendente/pago/cancelado)
    - Linha digitável (se boleto)
    - Empresa/filial

    **Exemplo de Uso (Python):**
    ```python
    # Cenário 1: Listar títulos pendentes a vencer
    pendentes = consultar_titulo_pagar(
        data_inicial="2025-01-10",
        data_final="2025-01-31",
        empresa_codigo=7,
        apenas_pendente=True,
        data_filtro="VENCIMENTO"
    )

    # Cenário 2: Listar todos os pagamentos do mês
    titulos = consultar_titulo_pagar(
        data_inicial="2025-01-01",
        data_final="2025-01-31",
        empresa_codigo=7
    )

    # Cenário 3: Fluxo de caixa - títulos a vencer nos próximos 7 dias
    import datetime
    hoje = datetime.date.today()
    proximos_7_dias = hoje + datetime.timedelta(days=7)
    
    a_vencer = consultar_titulo_pagar(
        data_inicial=hoje.strftime("%Y-%m-%d"),
        data_final=proximos_7_dias.strftime("%Y-%m-%d"),
        empresa_codigo=7,
        apenas_pendente=True,
        data_filtro="VENCIMENTO"
    )
    
    total_a_pagar = sum(t["saldoPendente"] for t in a_vencer)
    print(f"A pagar nos próximos 7 dias: R$ {total_a_pagar:,.2f}")
    ```

    **Dependências:**
    - Opcional: `consultar_empresas` (para obter empresa_codigo)
    - Opcional: `consultar_fornecedor` (para obter fornecedor_codigo)

    **Tools Relacionadas:**
    - `incluir_titulo_pagar` - Criar novo título a pagar
    - `consultar_fornecedor` - Consultar fornecedores

    **Dica:**
    Use `apenas_pendente=True` com `data_filtro="VENCIMENTO"` para planejamento de
    fluxo de caixa e gestão de pagamentos.
    """
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
    """
    **Cria um novo título a pagar.**

    Esta tool permite criar manualmente um título a pagar (boleto, nota fiscal, despesa)
    no sistema. É útil para lançamentos manuais ou integrações externas.

    **Quando usar:**
    - Para criar títulos de compras externas
    - Para lançamentos manuais de contas a pagar
    - Para despesas operacionais
    - Para integrações com outros sistemas

    **Fluxo de Uso Essencial:**
    1. **Prepare os Dados:** Monte o objeto com informações do título.
    2. **Crie o Título:** Chame `incluir_titulo_pagar` com os dados.

    **Parâmetros (via objeto `dados`):**
    - `fornecedorCodigo` (int, obrigatório): Código do fornecedor.
      Obter via: `consultar_fornecedor`
    - `valorOriginal` (float, obrigatório): Valor do título.
    - `dataEmissao` (str, obrigatório): Data de emissão (YYYY-MM-DD).
    - `dataVencimento` (str, obrigatório): Data de vencimento (YYYY-MM-DD).
    - `numeroDocumento` (str, opcional): Número do documento/nota.
    - `linhaDigitavel` (str, opcional): Linha digitável do boleto.
    - `observacao` (str, opcional): Observações.
    - `empresaCodigo` (int, opcional): Código da empresa.

    **Exemplo de Uso (Python):**
    ```python
    # Criar título a pagar
    resultado = incluir_titulo_pagar(
        dados={
            "fornecedorCodigo": 456,
            "valorOriginal": 5000.00,
            "dataEmissao": "2025-01-10",
            "dataVencimento": "2025-02-10",
            "numeroDocumento": "NF-123456",
            "linhaDigitavel": "34191.79001 01043.510047 91020.150008 1 96610000005000",
            "observacao": "Compra de combustível",
            "empresaCodigo": 7
        }
    )
    ```

    **Dependências:**
    - Requer: `consultar_fornecedor` (para obter fornecedorCodigo)
    - Opcional: `consultar_empresas` (para obter empresaCodigo)

    **Tools Relacionadas:**
    - `consultar_titulo_pagar` - Consultar títulos criados
    - `consultar_fornecedor` - Consultar fornecedores
    """
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
    """
    **Registra inventário de produto (contagem de estoque).**

    Esta tool permite registrar contagens de estoque (inventário) para ajustar o estoque
    do sistema com a contagem física. É essencial para controle de estoque e auditoria.

    **Quando usar:**
    - Para registrar contagens de inventário
    - Para ajustar estoque após contagem física
    - Para auditoria de estoque
    - Para conciliação de diferenças

    **Fluxo de Uso Essencial:**
    1. **Realize a Contagem Física:** Conte os produtos no estoque.
    2. **Registre o Inventário:** Chame `produto_inventario` com os dados da contagem.

    **Parâmetros (via objeto `dados`):**
    - `produtoCodigo` (int, obrigatório): Código do produto.
      Obter via: `consultar_produto`
    - `quantidadeContada` (float, obrigatório): Quantidade contada fisicamente.
    - `dataContagem` (str, obrigatório): Data da contagem (YYYY-MM-DD).
    - `empresaCodigo` (int, opcional): Código da empresa.
    - `observacao` (str, opcional): Observações sobre a contagem.

    **Exemplo de Uso (Python):**
    ```python
    # Registrar inventário de produto
    resultado = produto_inventario(
        dados={
            "produtoCodigo": 789,
            "quantidadeContada": 150.5,
            "dataContagem": "2025-01-10",
            "empresaCodigo": 7,
            "observacao": "Inventário mensal - Janeiro/2025"
        }
    )
    ```

    **Dependências:**
    - Requer: `consultar_produto` (para obter produtoCodigo)
    - Opcional: `consultar_empresas` (para obter empresaCodigo)

    **Tools Relacionadas:**
    - `consultar_produto_estoque` - Consultar estoque atual
    - `reajustar_estoque_produto_combustivel` - Ajustar estoque de combustíveis

    **Dica:**
    O sistema calculará automaticamente a diferença entre o estoque sistemático e a
    contagem física, gerando os ajustes necessários.
    """
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
    """
    **Consulta resumo agregado de vendas por empresa.**

    Esta tool retorna dados totalizados de vendas, agrupados por empresa/filial.
    É ideal para visão geral e comparação rápida entre filiais.

    **Diferença entre venda_resumo e consultar_venda:**
    - `venda_resumo`: Retorna dados agregados/totalizados por empresa (mais rápido)
    - `consultar_venda`: Retorna dados detalhados de cada venda individual (mais completo)

    **Quando usar:**
    - Para obter totais de vendas por filial rapidamente
    - Para comparação de performance entre empresas
    - Para dashboards e relatórios executivos
    - Quando não precisa de detalhes de cada transação

    **Fluxo de Uso Essencial:**
    1. **Obtenha IDs das Empresas (Opcional):** Use `consultar_empresas` se quiser filtrar
       empresas específicas.
    2. **Execute a Consulta:** Chame `venda_resumo` com o período desejado.

    **Parâmetros:**
    - `data_inicial` (str, opcional): Data de início no formato YYYY-MM-DD.
      Exemplo: "2025-01-10"
    - `data_final` (str, opcional): Data de fim no formato YYYY-MM-DD.
      Exemplo: "2025-01-10"
    - `empresa_codigo` (List[int], opcional): Lista de códigos de empresas para filtrar.
      Se não informado, retorna resumo de todas as empresas.
      Obter via: `consultar_empresas`
      Exemplo: [7, 8, 9]
    - `situacao` (str, opcional): Situação das vendas para filtrar.
      Valores válidos:
      * "A" - Ativo/Aberto
      * "F" - Finalizado
      * "C" - Cancelado
      Exemplo: "F"

    **Retorno:**
    Resumo agregado por empresa contendo:
    - Código da empresa
    - Nome da empresa
    - Quantidade total de vendas
    - Valor total vendido
    - Ticket médio
    - Período consultado

    **Exemplo de Uso (Python):**
    ```python
    # Cenário 1: Resumo de vendas do dia de todas as empresas
    resumo = venda_resumo(
        data_inicial="2025-01-10",
        data_final="2025-01-10"
    )

    # Cenário 2: Resumo de vendas finalizadas de empresas específicas
    resumo = venda_resumo(
        data_inicial="2025-01-01",
        data_final="2025-01-31",
        empresa_codigo=[7, 8],
        situacao="F"
    )

    # Cenário 3: Comparar performance de filiais no mês
    resumo_mes = venda_resumo(
        data_inicial="2025-01-01",
        data_final="2025-01-31"
    )
    # Resultado permite comparação rápida entre filiais
    ```

    **Dependências:**
    - Opcional: `consultar_empresas` (para obter empresa_codigo)

    **Dica de Performance:**
    Use `venda_resumo` quando precisar apenas de totais. É muito mais rápido que
    `consultar_venda` para grandes volumes de dados.
    """
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
    """
    **Consulta itens individuais de vendas.**

    Esta tool retorna os itens (produtos) vendidos em cada transação, permitindo análise
    detalhada de quais produtos foram vendidos, em que quantidade, preço e valor total.
    É essencial para relatórios de produtos mais vendidos e análise de mix de produtos.

    **Diferença entre consultar_venda e consultar_venda_item:**
    - `consultar_venda`: Retorna cabeçalho das vendas (data, cliente, total)
    - `consultar_venda_item`: Retorna itens/produtos de cada venda (detalhamento)

    **Quando usar:**
    - Para análise de produtos vendidos
    - Para relatórios de itens mais vendidos
    - Para auditoria de preços praticados
    - Para conciliação de estoque com vendas

    **Fluxo de Uso Essencial:**
    1. **Obtenha o ID da Empresa (Opcional):** Use `consultar_empresas` para filtrar.
    2. **Consulte Vendas (Opcional):** Use `consultar_venda` para obter códigos de vendas.
    3. **Execute a Consulta:** Chame `consultar_venda_item` com filtros desejados.

    **Parâmetros:**
    - `data_inicial` (str, opcional): Data de início no formato YYYY-MM-DD.
      Exemplo: "2025-01-10"
    - `data_final` (str, opcional): Data de fim no formato YYYY-MM-DD.
      Exemplo: "2025-01-10"
    - `empresa_codigo` (int, opcional): Código da empresa/filial para filtrar.
      Obter via: `consultar_empresas`
      Exemplo: 7
    - `venda_codigo` (List[int], opcional): Lista de códigos de vendas específicas.
      Útil para buscar itens de vendas conhecidas.
      Obter via: `consultar_venda`
      Exemplo: [12345, 12346]
    - `tipo_data` (str, opcional): Tipo de data para filtro.
      Valores: "FISCAL" ou "MOVIMENTO"
      Default: "FISCAL"
    - `usa_produto_lmc` (bool, opcional): Se True, usa código LMC do produto.
      Exemplo: False
    - `limite` (int, opcional): Número máximo de registros (default: 100, max: 2000).
    - `ultimo_codigo` (int, opcional): Para paginação, código do último item retornado.

    **Retorno:**
    Lista de itens de venda contendo:
    - Código do item
    - Código da venda (cabeçalho)
    - Código do produto
    - Descrição do produto
    - Quantidade vendida
    - Preço unitário
    - Valor total do item
    - Desconto aplicado
    - Data da venda
    - Empresa/filial

    **Exemplo de Uso (Python):**
    ```python
    # Cenário 1: Consultar todos os itens vendidos no dia
    itens = consultar_venda_item(
        data_inicial="2025-01-10",
        data_final="2025-01-10",
        empresa_codigo=7
    )

    # Cenário 2: Consultar itens de vendas específicas
    # Primeiro, obter vendas
    vendas = consultar_venda(
        data_inicial="2025-01-10",
        data_final="2025-01-10",
        empresa_codigo=7
    )
    venda_ids = [v["codigo"] for v in vendas[:5]]  # Primeiras 5 vendas
    
    # Depois, obter itens dessas vendas
    itens = consultar_venda_item(
        venda_codigo=venda_ids,
        empresa_codigo=7
    )

    # Cenário 3: Análise de produtos mais vendidos
    itens = consultar_venda_item(
        data_inicial="2025-01-01",
        data_final="2025-01-31",
        empresa_codigo=7
    )
    
    # Agrupar por produto
    from collections import defaultdict
    vendas_por_produto = defaultdict(lambda: {"quantidade": 0, "valor": 0})
    
    for item in itens:
        produto = item["produtoDescricao"]
        vendas_por_produto[produto]["quantidade"] += item["quantidade"]
        vendas_por_produto[produto]["valor"] += item["valorTotal"]
    
    # Ordenar por quantidade
    top_produtos = sorted(
        vendas_por_produto.items(),
        key=lambda x: x[1]["quantidade"],
        reverse=True
    )[:10]
    ```

    **Dependências:**
    - Opcional: `consultar_empresas` (para obter empresa_codigo)
    - Opcional: `consultar_venda` (para obter venda_codigo)

    **Tools Relacionadas:**
    - `consultar_venda` - Consulta cabeçalho das vendas
    - `vendas_periodo` - Relatório agregado de vendas
    - `consultar_produto` - Consulta detalhes dos produtos

    **Dica:**
    Esta tool é ideal para análises detalhadas de produtos vendidos. Para relatórios
    agregados, use `vendas_periodo` que é mais rápido.
    """
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
    """
    **Consulta vendas realizadas no período especificado.**

    Esta tool retorna todas as vendas (abastecimentos e produtos da loja de conveniência)
    realizadas em uma ou mais empresas/filiais do posto. É ideal para consultas detalhadas
    de transações individuais.

    **Diferença entre consultar_venda e venda_resumo:**
    - `consultar_venda`: Retorna dados detalhados de cada venda individual
    - `venda_resumo`: Retorna dados agregados/totalizados por empresa

    **Fluxo de Uso Essencial:**
    1. **Obtenha o ID da Empresa:** Use `consultar_empresas` para obter o `empresaCodigo`.
    2. **Execute a Consulta:** Chame `consultar_venda` com o período e filtros desejados.

    **Parâmetros Principais:**
    - `data_inicial` (str, opcional): Data de início no formato YYYY-MM-DD.
      Exemplo: "2025-01-10"
    - `data_final` (str, opcional): Data de fim no formato YYYY-MM-DD.
      Deve ser maior ou igual a data_inicial.
      Exemplo: "2025-01-10"
    - `empresa_codigo` (int, opcional): Código da empresa/filial para filtrar.
      Se não informado, retorna vendas de todas as empresas.
      Obter via: `consultar_empresas`
      Exemplo: 7
    - `situacao` (str, opcional): Situação da venda para filtrar.
      Valores válidos:
      * "A" - Ativo/Aberto (venda em andamento)
      * "F" - Finalizado (venda concluída)
      * "C" - Cancelado (venda cancelada)
      Se não informado, retorna todas as situações.
      Exemplo: "F"
    - `tipo_data` (str, opcional): Tipo de data para filtro.
      Valores: "FISCAL" ou "MOVIMENTO"
      Default: "FISCAL"
    - `turno` (int, opcional): Filtrar por turno específico.
    - `limite` (int, opcional): Número máximo de registros (default: 100, max: 2000).
    - `ultimo_codigo` (int, opcional): Para paginação, código da última venda retornada.

    **Retorno:**
    Lista de vendas com informações detalhadas:
    - Código da venda
    - Data e hora
    - Valor total
    - Situação
    - Empresa/filial
    - Cliente (se houver)
    - Itens da venda

    **Exemplo de Uso (Python):**
    ```python
    # Cenário 1: Consultar vendas do dia atual de todas as empresas
    vendas = consultar_venda(
        data_inicial="2025-01-10",
        data_final="2025-01-10"
    )

    # Cenário 2: Consultar vendas finalizadas de uma empresa específica
    vendas = consultar_venda(
        data_inicial="2025-01-01",
        data_final="2025-01-10",
        empresa_codigo=7,
        situacao="F"
    )

    # Cenário 3: Consultar vendas com paginação
    primeira_pagina = consultar_venda(
        data_inicial="2025-01-01",
        data_final="2025-01-31",
        limite=100
    )
    # Obter próxima página
    segunda_pagina = consultar_venda(
        data_inicial="2025-01-01",
        data_final="2025-01-31",
        limite=100,
        ultimo_codigo=primeira_pagina[-1]["codigo"]
    )
    ```

    **Dependências:**
    - Opcional: `consultar_empresas` (para obter empresa_codigo)

    **Erros Comuns:**
    - Erro se data_inicial > data_final
    - Erro se empresa_codigo não existe
    - Erro se situacao tem valor inválido
    """
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
    """
    **Consulta tanques de armazenamento de combustível.**

    Esta tool retorna a lista de tanques (reservatórios subterrâneos que armazenam
    combustíveis) cadastrados no sistema. Cada tanque armazena um tipo específico de
    combustível e abastece uma ou mais bombas.

    **Quando usar:**
    - Para listar tanques de uma empresa/filial
    - Para obter ID de tanque para relatórios de estoque
    - Para controle de capacidade e nível de combustível
    - Para gestão de ativos e manutenção

    **Hierarquia de Equipamentos:**
    **Tanque** (armazenamento) → Bomba → Bico (abastecimento)

    **Fluxo de Uso Essencial:**
    1. **Obtenha o ID da Empresa (Opcional):** Use `consultar_empresas` para filtrar.
    2. **Execute a Consulta:** Chame `consultar_tanque` com os filtros desejados.

    **Parâmetros:**
    - `empresa_codigo` (int, opcional): Código da empresa/filial para filtrar.
      Se não informado, retorna tanques de todas as empresas.
      Obter via: `consultar_empresas`
      Exemplo: 7
    - `tanque_codigo` (int, opcional): Código de um tanque específico.
      Útil para buscar detalhes de um tanque conhecido.
      Exemplo: 1
    - `limite` (int, opcional): Número máximo de registros (default: 100, max: 2000).
    - `ultimo_codigo` (int, opcional): Para paginação, código do último tanque retornado.

    **Retorno:**
    Lista de tanques contendo:
    - Código do tanque
    - Descrição/identificação (ex: "Tanque 1 - Gasolina")
    - Produto combustível armazenado
    - Capacidade total (litros)
    - Nível atual (litros)
    - Percentual de ocupação
    - Empresa/filial
    - Status (ativo/inativo)
    - Bombas vinculadas

    **Exemplo de Uso (Python):**
    ```python
    # Cenário 1: Listar todos os tanques de uma empresa
    tanques = consultar_tanque(
        empresa_codigo=7
    )

    # Cenário 2: Buscar um tanque específico
    tanque = consultar_tanque(
        tanque_codigo=1,
        empresa_codigo=7
    )

    # Cenário 3: Verificar níveis de combustível
    tanques = consultar_tanque(empresa_codigo=7)
    for tanque in tanques:
        produto = tanque["produtoDescricao"]
        nivel = tanque["nivelAtual"]
        capacidade = tanque["capacidadeTotal"]
        percentual = (nivel / capacidade) * 100
        
        if percentual < 20:
            print(f"ALERTA: {produto} com apenas {percentual:.1f}% de capacidade")

    # Cenário 4: Relatório de estoque por tanque
    tanques = consultar_tanque(empresa_codigo=7)
    for tanque in tanques:
        print(f"Tanque: {tanque['descricao']}")
        print(f"Produto: {tanque['produtoDescricao']}")
        print(f"Estoque: {tanque['nivelAtual']} litros")
    ```

    **Dependências:**
    - Opcional: `consultar_empresas` (para obter empresa_codigo)

    **Tools Relacionadas:**
    - `consultar_bomba` - Consulta bombas abastecidas pelos tanques
    - `consultar_bico` - Consulta bicos de abastecimento
    - `consultar_produto_combustivel` - Consulta produtos armazenados

    **Dica:**
    Use esta tool para monitoramento de estoque de combustível e alertas de
    reabastecimento. Tanques com nível abaixo de 20% geralmente precisam de pedido.
    """
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
    """
    **Consulta PDVs (Pontos de Venda / Caixas) cadastrados.**

    Esta tool retorna a lista de PDVs/Caixas (terminais onde as vendas são registradas)
    cadastrados no sistema. Cada PDV pode ser um caixa da loja de conveniência ou um
    terminal de controle da pista.

    **Quando usar:**
    - Para listar PDVs/caixas de uma empresa/filial
    - Para obter ID de PDV antes de filtrar vendas por caixa
    - Para relatórios de performance por caixa
    - Para controle de equipamentos e terminais

    **Tipos de PDV:**
    - **Caixa da Loja**: Terminal da loja de conveniência
    - **Caixa da Pista**: Terminal de controle de abastecimentos
    - **PDV Móvel**: Terminais portáteis (se aplicável)

    **Fluxo de Uso Essencial:**
    1. **Obtenha o ID da Empresa (Opcional):** Use `consultar_empresas` para filtrar.
    2. **Execute a Consulta:** Chame `consultar_pdv` com os filtros desejados.

    **Parâmetros:**
    - `empresa_codigo` (int, opcional): Código da empresa/filial para filtrar.
      Se não informado, retorna PDVs de todas as empresas.
      Obter via: `consultar_empresas`
      Exemplo: 7
    - `pdv_codigo` (int, opcional): Código de um PDV específico.
      Útil para buscar detalhes de um PDV conhecido.
      Exemplo: 1
    - `pdv_referencia` (str, opcional): Referência/identificação externa do PDV.
      Exemplo: "CAIXA-01"
    - `limite` (int, opcional): Número máximo de registros (default: 100, max: 2000).
    - `ultimo_codigo` (int, opcional): Para paginação, código do último PDV retornado.

    **Retorno:**
    Lista de PDVs contendo:
    - Código do PDV
    - Descrição/identificação (ex: "Caixa 1", "PDV Loja")
    - Referência externa
    - Empresa/filial
    - Tipo de PDV (loja/pista)
    - Status (ativo/inativo)
    - Operador/funcionário atual (se em uso)

    **Exemplo de Uso (Python):**
    ```python
    # Cenário 1: Listar todos os PDVs de uma empresa
    pdvs = consultar_pdv(
        empresa_codigo=7
    )

    # Cenário 2: Buscar um PDV específico por código
    pdv = consultar_pdv(
        pdv_codigo=1,
        empresa_codigo=7
    )

    # Cenário 3: Buscar PDV por referência
    pdv = consultar_pdv(
        pdv_referencia="CAIXA-01",
        empresa_codigo=7
    )

    # Cenário 4: Relatório de vendas por caixa
    pdvs = consultar_pdv(empresa_codigo=7)
    pdv_ids = [p["codigo"] for p in pdvs]

    # Usar IDs em relatório de vendas
    vendas_por_caixa = vendas_periodo(
        data_inicial="2025-01-01",
        data_final="2025-01-31",
        filial=[7],
        pdv_caixa=pdv_ids,
        tipo_data="FISCAL",
        ordenacao_por="QUANTIDADE_VENDIDA",
        cupom_cancelado=False,
        agrupamento_por="SEM_AGRUPAMENTO"
    )
    ```

    **Dependências:**
    - Opcional: `consultar_empresas` (para obter empresa_codigo)

    **Tools Relacionadas:**
    - `vendas_periodo` - Filtrar vendas por PDV/caixa
    - `consultar_venda` - Consultar vendas com filtro de PDV
    - `consultar_funcionario` - Consultar operadores de caixa

    **Dica:**
    Use esta tool para identificar caixas ativos e gerar relatórios de performance
    por terminal. É útil para análise de produtividade e controle operacional.
    """
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
    """
    **Consulta funcionários cadastrados no sistema.**

    Esta tool retorna a lista de funcionários (frentistas, operadores de caixa, gerentes, etc.)
    cadastrados no sistema. É essencial para obter IDs de funcionários antes de filtrar
    relatórios de vendas, abastecimentos ou produtividade.

    **Quando usar:**
    - Para listar funcionários de uma empresa/filial
    - Para obter ID de funcionário antes de gerar relatórios
    - Para validação de funcionários em operações
    - Para relatórios de produtividade por funcionário

    **Fluxo de Uso Essencial:**
    1. **Obtenha o ID da Empresa (Opcional):** Use `consultar_empresas` para filtrar por empresa.
    2. **Execute a Consulta:** Chame `consultar_funcionario` com os filtros desejados.

    **Parâmetros:**
    - `empresa_codigo` (int, opcional): Código da empresa/filial para filtrar.
      Se não informado, retorna funcionários de todas as empresas.
      Obter via: `consultar_empresas`
      Exemplo: 7
    - `funcionario_codigo` (int, opcional): Código de um funcionário específico.
      Útil para buscar detalhes de um funcionário conhecido.
      Exemplo: 123
    - `limite` (int, opcional): Número máximo de registros (default: 100, max: 2000).
    - `ultimo_codigo` (int, opcional): Para paginação, código do último funcionário retornado.

    **Retorno:**
    Lista de funcionários contendo:
    - Código do funcionário
    - Nome completo
    - CPF
    - Função/cargo (ex: "Frentista", "Gerente", "Caixa")
    - Empresa/filial vinculada
    - Status (ativo/inativo)
    - Data de admissão

    **Exemplo de Uso (Python):**
    ```python
    # Cenário 1: Listar todos os funcionários de uma empresa
    funcionarios = consultar_funcionario(
        empresa_codigo=7
    )

    # Cenário 2: Buscar um funcionário específico
    funcionario = consultar_funcionario(
        funcionario_codigo=123
    )

    # Cenário 3: Listar frentistas para relatório de produtividade
    funcionarios = consultar_funcionario(
        empresa_codigo=7
    )
    # Filtrar frentistas (se necessário, filtrar por função no resultado)
    frentistas = [f for f in funcionarios if "Frentista" in f.get("funcao", "")]
    frentista_ids = [f["codigo"] for f in frentistas]

    # Usar IDs em relatório de vendas
    vendas_por_frentista = vendas_periodo(
        data_inicial="2025-01-01",
        data_final="2025-01-31",
        filial=[7],
        funcionario=frentista_ids,
        tipo_data="FISCAL",
        ordenacao_por="QUANTIDADE_VENDIDA",
        cupom_cancelado=False
    )
    ```

    **Dependências:**
    - Opcional: `consultar_empresas` (para obter empresa_codigo)

    **Uso Comum:**
    Esta tool é frequentemente usada em conjunto com:
    - `vendas_periodo` (filtrar vendas por funcionário)
    - `abastecimento` (filtrar abastecimentos por frentista)
    - Relatórios de produtividade

    **Dica:**
    Funcionários inativos também são retornados. Verifique o campo `status` se
    precisar apenas de funcionários ativos.
    """
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
    """
    **Consulta o estoque de produtos em uma data específica.**

    Esta tool retorna a posição de estoque (quantidade disponível) de produtos em uma
    determinada data. É ideal para consultas históricas de estoque e acompanhamento de
    movimentações.

    **Quando usar:**
    - Para verificar estoque em uma data específica
    - Para auditoria de movimentações de estoque
    - Para relatórios históricos de posição
    - Para reconciliação de inventário

    **Fluxo de Uso Essencial:**
    1. **Obtenha o ID da Empresa (Opcional):** Use `consultar_empresas` se quiser filtrar
       por empresa específica.
    2. **Execute a Consulta:** Chame `estoque_periodo` com a data desejada.

    **Parâmetros:**
    - `data_final` (str, obrigatório): Data de referência para consulta do estoque.
      Formato: YYYY-MM-DD
      Retorna o estoque na posição desta data.
      Exemplo: "2025-01-10"
    - `empresa_codigo` (int, opcional): Código da empresa/filial para filtrar.
      Se não informado, retorna estoque de todas as empresas.
      Obter via: `consultar_empresas`
      Exemplo: 7
    - `data_hora_atualizacao` (str, opcional): Filtrar por data/hora de atualização.
      Formato: YYYY-MM-DD HH:MM:SS
      Útil para sincronização incremental.
      Exemplo: "2025-01-10 14:30:00"
    - `limite` (int, opcional): Número máximo de registros (default: 100, max: 2000).
    - `ultimo_codigo` (int, opcional): Para paginação, código do último registro retornado.

    **Retorno:**
    Lista de produtos com informações de estoque:
    - Código do produto
    - Descrição do produto
    - Quantidade em estoque
    - Unidade de medida
    - Empresa/filial
    - Data de referência
    - Valor unitário (custo)
    - Valor total em estoque

    **Exemplo de Uso (Python):**
    ```python
    # Cenário 1: Consultar estoque atual de todas as empresas
    estoque_hoje = estoque_periodo(
        data_final="2025-01-10"
    )

    # Cenário 2: Consultar estoque de uma empresa específica
    estoque_filial = estoque_periodo(
        data_final="2025-01-10",
        empresa_codigo=7
    )

    # Cenário 3: Consultar estoque histórico (final do mês anterior)
    estoque_mes_anterior = estoque_periodo(
        data_final="2024-12-31",
        empresa_codigo=7
    )

    # Cenário 4: Sincronização incremental
    estoque_atualizado = estoque_periodo(
        data_final="2025-01-10",
        data_hora_atualizacao="2025-01-10 08:00:00"
    )
    ```

    **Dependências:**
    - Opcional: `consultar_empresas` (para obter empresa_codigo)

    **Diferença entre estoque_periodo e estoque:**
    - `estoque_periodo`: Consulta estoque em uma data específica (histórico)
    - `estoque`: Consulta cadastro de estoques (locais de armazenamento)

    **Dica:**
    Para verificar estoque atual, use a data de hoje em `data_final`.
    """
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
    """
    **Consulta bombas de combustível cadastradas.**

    Esta tool retorna a lista de bombas de combustível (equipamentos que contêm os bicos
    de abastecimento) cadastradas no sistema. Cada bomba pode ter múltiplos bicos.

    **Quando usar:**
    - Para listar bombas de uma empresa/filial
    - Para obter ID de bomba antes de consultar bicos
    - Para relatórios de equipamentos
    - Para manutenção e controle de ativos

    **Hierarquia de Equipamentos:**
    Tanque → Bomba → Bico (onde o abastecimento acontece)

    **Fluxo de Uso Essencial:**
    1. **Obtenha o ID da Empresa (Opcional):** Use `consultar_empresas` para filtrar.
    2. **Execute a Consulta:** Chame `consultar_bomba` com os filtros desejados.

    **Parâmetros:**
    - `empresa_codigo` (int, opcional): Código da empresa/filial para filtrar.
      Se não informado, retorna bombas de todas as empresas.
      Obter via: `consultar_empresas`
      Exemplo: 7
    - `bomba_codigo` (int, opcional): Código de uma bomba específica.
      Útil para buscar detalhes de uma bomba conhecida.
      Exemplo: 1

    **Retorno:**
    Lista de bombas contendo:
    - Código da bomba
    - Descrição/identificação
    - Empresa/filial
    - Status (ativa/inativa)
    - Bicos vinculados
    - Tanque associado

    **Exemplo de Uso (Python):**
    ```python
    # Cenário 1: Listar todas as bombas de uma empresa
    bombas = consultar_bomba(
        empresa_codigo=7
    )

    # Cenário 2: Buscar uma bomba específica
    bomba = consultar_bomba(
        bomba_codigo=1,
        empresa_codigo=7
    )

    # Cenário 3: Listar bombas para depois consultar bicos
    bombas = consultar_bomba(empresa_codigo=7)
    for bomba in bombas:
        bomba_id = bomba["codigo"]
        # Consultar bicos desta bomba
        bicos = consultar_bico(empresa_codigo=7)
        bicos_da_bomba = [b for b in bicos if b.get("bombaCodigo") == bomba_id]
    ```

    **Dependências:**
    - Opcional: `consultar_empresas` (para obter empresa_codigo)

    **Tools Relacionadas:**
    - `consultar_bico` - Consulta bicos vinculados às bombas
    - `consultar_tanque` - Consulta tanques que abastecem as bombas
    - `abastecimento` - Consulta abastecimentos realizados nos bicos
    """
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
    """
    **Consulta bicos de abastecimento cadastrados.**

    Esta tool retorna a lista de bicos de abastecimento (pontos onde o combustível é
    efetivamente abastecido nos veículos) cadastrados no sistema. Cada bico está vinculado
    a uma bomba e a um produto combustível.

    **Quando usar:**
    - Para listar bicos de uma empresa/filial
    - Para obter ID de bico antes de filtrar abastecimentos
    - Para relatórios de produção por bico
    - Para controle de equipamentos

    **Hierarquia de Equipamentos:**
    Tanque → Bomba → **Bico** (onde o abastecimento acontece)

    **Fluxo de Uso Essencial:**
    1. **Obtenha o ID da Empresa (Opcional):** Use `consultar_empresas` para filtrar.
    2. **Execute a Consulta:** Chame `consultar_bico` com os filtros desejados.

    **Parâmetros:**
    - `empresa_codigo` (int, opcional): Código da empresa/filial para filtrar.
      Se não informado, retorna bicos de todas as empresas.
      Obter via: `consultar_empresas`
      Exemplo: 7
    - `bico_codigo` (int, opcional): Código de um bico específico.
      Útil para buscar detalhes de um bico conhecido.
      Exemplo: 101
    - `limite` (int, opcional): Número máximo de registros (default: 100, max: 2000).
    - `ultimo_codigo` (int, opcional): Para paginação, código do último bico retornado.

    **Retorno:**
    Lista de bicos contendo:
    - Código do bico
    - Número/identificação do bico
    - Bomba vinculada
    - Produto combustível
    - Empresa/filial
    - Status (ativo/inativo)
    - Encerrante (leitura do totalizador)

    **Exemplo de Uso (Python):**
    ```python
    # Cenário 1: Listar todos os bicos de uma empresa
    bicos = consultar_bico(
        empresa_codigo=7
    )

    # Cenário 2: Buscar um bico específico
    bico = consultar_bico(
        bico_codigo=101,
        empresa_codigo=7
    )

    # Cenário 3: Listar bicos de gasolina para relatório
    bicos = consultar_bico(empresa_codigo=7)
    # Filtrar por produto (exemplo)
    bicos_gasolina = [b for b in bicos if "Gasolina" in b.get("produtoDescricao", "")]
    bico_ids = [b["codigo"] for b in bicos_gasolina]

    # Usar IDs em relatório de abastecimentos
    abastecimentos = abastecimento(
        data_inicial="2025-01-01",
        data_final="2025-01-31",
        empresa_codigo=7
    )
    # Filtrar por bicos de gasolina
    abast_gasolina = [a for a in abastecimentos if a.get("bicoCodigo") in bico_ids]
    ```

    **Dependências:**
    - Opcional: `consultar_empresas` (para obter empresa_codigo)

    **Tools Relacionadas:**
    - `consultar_bomba` - Consulta bombas que contêm os bicos
    - `consultar_tanque` - Consulta tanques de armazenamento
    - `abastecimento` - Consulta abastecimentos realizados nos bicos

    **Dica:**
    Bicos são identificados por número (ex: Bico 1, Bico 2). Use este número para
    comunicação com usuários finais, mas use o `codigo` para filtros em APIs.
    """
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
    """
    **Consulta abastecimentos realizados na pista.**

    Esta tool retorna todos os abastecimentos de combustível realizados na pista do posto.
    É uma das tools mais importantes para análise de vendas de combustíveis, controle de
    estoque e performance de frentistas.

    **Quando usar:**
    - Para relatórios de abastecimentos
    - Para análise de vendas de combustível
    - Para controle de performance de frentistas
    - Para conciliação de estoque vs vendas
    - Para auditoria de operações da pista

    **Fluxo de Uso Essencial:**
    1. **Execute a Consulta:** Chame `consultar_abastecimento` com o período desejado.
    2. **Analise os Dados:** Use os dados para relatórios e análises.

    **Parâmetros:**
    - `data_inicial` (str, obrigatório): Data de início no formato YYYY-MM-DD.
      Exemplo: "2025-01-10"
    - `data_final` (str, obrigatório): Data de fim no formato YYYY-MM-DD.
      Exemplo: "2025-01-10"
    - `tipo_data` (str, opcional): Tipo de data para filtro.
      Valores: "FISCAL" ou "MOVIMENTO"
      Default: "FISCAL"
    - `limite` (int, opcional): Número máximo de registros (default: 100, max: 2000).
    - `ultimo_codigo` (int, opcional): Para paginação, código do último abastecimento.

    **Retorno:**
    Lista de abastecimentos contendo:
    - Código do abastecimento
    - Data e hora
    - Bico utilizado
    - Bomba
    - Produto combustível (Gasolina, Diesel, Etanol, etc.)
    - Quantidade (litros)
    - Preço unitário (por litro)
    - Valor total
    - Frentista responsável
    - Placa do veículo (se informada)
    - Cliente (se identificado)
    - Forma de pagamento
    - Empresa/filial

    **Exemplo de Uso (Python):**
    ```python
    # Cenário 1: Consultar abastecimentos do dia
    abastecimentos = consultar_abastecimento(
        data_inicial="2025-01-10",
        data_final="2025-01-10"
    )

    # Cenário 2: Relatório mensal de abastecimentos
    abastecimentos = consultar_abastecimento(
        data_inicial="2025-01-01",
        data_final="2025-01-31",
        tipo_data="FISCAL"
    )

    # Cenário 3: Análise por produto
    abastecimentos = consultar_abastecimento(
        data_inicial="2025-01-01",
        data_final="2025-01-31"
    )
    
    # Agrupar por produto
    from collections import defaultdict
    vendas_por_produto = defaultdict(lambda: {"litros": 0, "valor": 0})
    
    for abast in abastecimentos:
        produto = abast["produtoDescricao"]
        vendas_por_produto[produto]["litros"] += abast["quantidade"]
        vendas_por_produto[produto]["valor"] += abast["valorTotal"]
    
    # Mostrar resultados
    for produto, dados in vendas_por_produto.items():
        print(f"{produto}: {dados['litros']:.2f}L - R$ {dados['valor']:.2f}")

    # Cenário 4: Performance de frentistas
    abastecimentos = consultar_abastecimento(
        data_inicial="2025-01-01",
        data_final="2025-01-31"
    )
    
    vendas_por_frentista = defaultdict(lambda: {"quantidade": 0, "valor": 0})
    
    for abast in abastecimentos:
        frentista = abast.get("frentistaNome", "Não identificado")
        vendas_por_frentista[frentista]["quantidade"] += 1
        vendas_por_frentista[frentista]["valor"] += abast["valorTotal"]
    
    # Ranking de frentistas
    ranking = sorted(
        vendas_por_frentista.items(),
        key=lambda x: x[1]["valor"],
        reverse=True
    )
    ```

    **Dependências:**
    Nenhuma. Esta tool pode ser chamada diretamente.

    **Tools Relacionadas:**
    - `consultar_bico` - Consultar bicos de abastecimento
    - `consultar_bomba` - Consultar bombas
    - `consultar_produto_combustivel` - Consultar produtos combustíveis
    - `consultar_funcionario` - Consultar frentistas
    - `vendas_periodo` - Relatório agregado de vendas (inclui abastecimentos)

    **Dica:**
    Esta tool retorna dados transacionais detalhados. Para relatórios agregados e
    análises complexas, considere usar `vendas_periodo` que é mais rápido e oferece
    múltiplos agrupamentos.
    """
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
    """
    **Consulta produtos combustíveis disponíveis para pedidos.**

    Esta tool retorna a lista de produtos combustíveis cadastrados no sistema que podem
    ser utilizados em pedidos de combustível. É específica para o módulo de pedidos e
    difere de `consultar_produto` que retorna todos os produtos.

    **Quando usar:**
    - Para listar combustíveis disponíveis para pedidos
    - Para obter IDs de produtos combustíveis antes de criar pedidos
    - Para validação de produtos em integrações de pedidos

    **Diferença entre consultar_produto_combustivel e consultar_produto:**
    - `consultar_produto_combustivel`: Apenas combustíveis do módulo de pedidos (sem parâmetros)
    - `consultar_produto`: Todos os produtos (combustíveis + loja), permite filtros por empresa

    **Fluxo de Uso Essencial:**
    1. **Execute a Consulta:** Chame `consultar_produto_combustivel` diretamente.
    2. **Use os IDs:** Utilize os códigos retornados em operações de pedidos de combustível.

    **Parâmetros:**
    Esta tool não possui parâmetros. Retorna todos os produtos combustíveis cadastrados.

    **Retorno:**
    Lista de produtos combustíveis contendo:
    - Código do produto
    - Descrição (ex: "Gasolina Comum", "Diesel S10", "Etanol")
    - Tipo de combustível
    - Unidade de medida
    - Status (ativo/inativo)

    **Exemplo de Uso (Python):**
    ```python
    # Cenário 1: Listar todos os combustíveis disponíveis
    combustiveis = consultar_produto_combustivel()
    print(combustiveis)
    # Resultado: [{"codigo": 150, "descricao": "Gasolina Comum"}, ...]

    # Cenário 2: Buscar ID de um combustível específico
    combustiveis = consultar_produto_combustivel()
    gasolina = next(c for c in combustiveis if "Gasolina" in c["descricao"])
    gasolina_id = gasolina["codigo"]

    # Cenário 3: Validar se um produto é combustível válido para pedidos
    combustiveis = consultar_produto_combustivel()
    ids_validos = [c["codigo"] for c in combustiveis]
    if produto_id in ids_validos:
        print("Produto válido para pedido de combustível")
    ```

    **Dependências:**
    Nenhuma. Esta tool pode ser chamada diretamente.

    **Uso Recomendado:**
    - Use esta tool quando trabalhar com o módulo de pedidos de combustível
    - Para outros casos, use `consultar_produto` com filtro `tipo_produto=["COMBUSTIVEL"]`

    **Dica:**
    Os IDs retornados aqui são os mesmos usados em `consultar_produto`, mas esta tool
    é mais rápida por retornar apenas combustíveis.
    """
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
    """
    **Gera um relatório detalhado de vendas por período.**

    Esta tool é uma das mais poderosas e complexas, permitindo a extração de dados de vendas
    com múltiplos filtros, agrupamentos e ordenações. Para utilizá-la corretamente, é crucial
    entender suas dependências.

    **Fluxo de Uso Essencial:**
    1. **Obtenha o ID da Empresa:** Primeiro, use a tool `consultar_empresas` para listar as
       empresas (filiais) e obter o `empresaCodigo` desejado.
    2. **Consulte IDs para Filtros (Opcional):** Se precisar filtrar por produto, cliente,
       funcionário, etc., use as tools de consulta correspondentes (`consultar_produto`,
       `consultar_cliente`) para obter os IDs antes de chamar esta tool.
    3. **Execute a Consulta:** Chame `vendas_periodo` com as datas, o `empresaCodigo`
       (no parâmetro `filial`) e outros filtros desejados.

    **Parâmetros Principais:**
    - `data_inicial` (str, obrigatório): Data de início do período (formato: 'YYYY-MM-DD').
    - `data_final` (str, obrigatório): Data de fim do período (formato: 'YYYY-MM-DD').
    - `filial` (List[int], obrigatório): Lista de IDs de empresas/filiais a serem incluídas.
      Obtenha os IDs com a tool `consultar_empresas`.
    - `tipo_data` (str, obrigatório): Define a referência de data. Valores: 'FISCAL' ou 'MOVIMENTO'.
    - `ordenacao_por` (str, obrigatório): Critério de ordenação. Valores: 'REFERENCIA',
      'PRODUTO', 'PARTICIPACAO', 'QUANTIDADE_VENDIDA'.
    - `cupom_cancelado` (bool, obrigatório): Se `True`, inclui cupons cancelados no relatório.

    **Parâmetros de Agrupamento e Filtro (Opcionais):**
    - `agrupamento_por` (str): Agrupa os resultados. Ex: 'PRODUTO', 'CLIENTE', 'DIA', 'MES'.
      Default: 'SEM_AGRUPAMENTO'.
    - `produto` (List[int]): Lista de IDs de produtos para filtrar. Use `consultar_produto`
      para obter os IDs.
    - `cliente` (int): ID de um cliente específico. Use `consultar_cliente` para obter o ID.
    - `funcionario` (List[int]): Lista de IDs de funcionários. Use `consultar_funcionario`
      para obter os IDs.
    - `grupo_produto` (List[int]): Lista de IDs de grupos de produtos. Use
      `consultar_grupo_produto` para obter os IDs.
    - `tipo_produto` (List[str]): Filtra por tipo de produto. Ex: ['COMBUSTIVEL'],
      ['PRODUTO', 'SERVICO'].
    - `depto_selcon` (str): Filtra por departamento. Valores: 'PISTA' (combustíveis),
      'LOJA' (conveniência), 'AMBOS'.

    **Exemplo de Uso (Python):**
    ```python
    # Cenário: Gerar um relatório de vendas de combustível para a filial 1, agrupado por produto.

    # 1. Obter ID da empresa
    # empresas = consultar_empresas()
    # id_filial_1 = 7  # Supondo que o ID da filial desejada seja 7

    # 2. Chamar a tool de vendas
    relatorio = vendas_periodo(
        data_inicial='2025-12-01',
        data_final='2025-12-31',
        filial=[7],
        tipo_data='FISCAL',
        ordenacao_por='QUANTIDADE_VENDIDA',
        cupom_cancelado=False,
        agrupamento_por='PRODUTO',
        tipo_produto=['COMBUSTIVEL']
    )
    print(relatorio)
    ```

    **Dependências:**
    - Requer: `consultar_empresas` (para obter filial)
    - Opcional: `consultar_produto`, `consultar_cliente`, `consultar_funcionario`,
      `consultar_grupo_produto` (para filtros específicos)
    """
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
    # Aviso se API_KEY não estiver configurada (não bloqueia para permitir inspeção)
    if not API_KEY:
        logger.warning("=" * 60)
        logger.warning("AVISO: WEBPOSTO_API_KEY não configurada!")
        logger.warning("As ferramentas não funcionarão sem a chave de API.")
        logger.warning("Defina a variável de ambiente WEBPOSTO_API_KEY")
        logger.warning("=" * 60)
    else:
        logger.info("=" * 60)
        logger.info("WebPosto MCP Server - Quality Automação v1.3.0")
        logger.info("=" * 60)
        logger.info(f"URL Base: {WEBPOSTO_BASE_URL}")
        logger.info(f"Chave API: {'*' * 8}...{API_KEY[-8:] if len(API_KEY) > 8 else '****'}")
        logger.info("=" * 60)
    
    mcp.run()

if __name__ == "__main__":
    main()
