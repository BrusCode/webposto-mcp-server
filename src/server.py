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

# Importar resources e prompts
try:
    from src.resources_prompts import (
        get_resources_list,
        read_resource,
        get_prompts_list,
        get_prompt
    )
except ImportError:
    from resources_prompts import (
        get_resources_list,
        read_resource,
        get_prompts_list,
        get_prompt
    )

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
    
    def _normalize_params(self, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Normaliza parâmetros para compatibilidade com a API WebPosto.
        
        Converte booleanos Python (True/False) para strings minúsculas (true/false)
        que a API WebPosto espera.
        """
        if params is None:
            return {}
        
        normalized = {}
        for key, value in params.items():
            if isinstance(value, bool):
                # Converter booleano Python para string minúscula
                normalized[key] = str(value).lower()
            elif isinstance(value, list):
                # Processar listas recursivamente
                normalized[key] = [str(v).lower() if isinstance(v, bool) else v for v in value]
            else:
                normalized[key] = value
        return normalized
    
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
        # Normalizar parâmetros (converter booleanos para strings minúsculas)
        params = self._normalize_params(params)
        # Adicionar autenticação
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
# RESOURCES - Documentação e Schemas
# =============================================================================

@mcp.resource("file:///docs/{filename}")
def get_documentation(filename: str) -> str:
    """
    Retorna documentação do sistema webPosto.
    
    Resources disponíveis:
    - GUIA_USO_APIS.md: Guia completo de uso das APIs
    - mapeamento_dependencias_apis.md: Mapeamento de dependências
    - prompt_agente_webposto.md: Prompt otimizado para agentes
    """
    uri = f"file:///docs/{filename}"
    return read_resource(uri)

@mcp.resource("schema://tools")
def get_tools_schema() -> str:
    """
    Retorna o schema JSON com todas as tools disponíveis.
    """
    return read_resource("schema://tools")

# =============================================================================
# PROMPTS - Templates Pré-configurados
# =============================================================================

@mcp.prompt()
def analise_vendas(periodo: str = "últimos 30 dias", unidade_negocio: str = "todas") -> str:
    """
    Prompt para análise completa de vendas e faturamento.
    
    Args:
        periodo: Período para análise (ex: 'últimos 30 dias', 'mês atual')
        unidade_negocio: Código da unidade de negócio (opcional)
    """
    return get_prompt("analise_vendas", {
        "periodo": periodo,
        "unidade_negocio": unidade_negocio
    })

@mcp.prompt()
def consulta_estoque(tipo_produto: str = "todos", unidade_negocio: str = "todas") -> str:
    """
    Prompt para consulta detalhada de estoque e produtos.
    
    Args:
        tipo_produto: Tipo de produto (combustível, conveniência, todos)
        unidade_negocio: Código da unidade de negócio (opcional)
    """
    return get_prompt("consulta_estoque", {
        "tipo_produto": tipo_produto,
        "unidade_negocio": unidade_negocio
    })

@mcp.prompt()
def relatorio_financeiro(periodo: str = "mês atual", tipo: str = "ambos") -> str:
    """
    Prompt para relatório financeiro completo.
    
    Args:
        periodo: Período para análise (ex: 'mês atual', 'próximos 7 dias')
        tipo: Tipo de relatório (pagar, receber, ambos)
    """
    return get_prompt("relatorio_financeiro", {
        "periodo": periodo,
        "tipo": tipo
    })

@mcp.prompt()
def analise_abastecimento(periodo: str = "últimos 7 dias", bomba_codigo: str = "todas") -> str:
    """
    Prompt para análise detalhada de abastecimentos.
    
    Args:
        periodo: Período para análise
        bomba_codigo: Código da bomba (opcional, para análise específica)
    """
    return get_prompt("analise_abastecimento", {
        "periodo": periodo,
        "bomba_codigo": bomba_codigo
    })

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
    """
    **Recebe título a receber convertido (baixa com conversão).**

    Esta tool permite dar baixa em títulos a receber que foram convertidos para
    outras formas de pagamento (ex: duplicata convertida em cartão, cheque, etc.).
    É usado quando o cliente paga uma duplicata com forma de pagamento diferente.

    **Quando usar:**
    - Para baixar duplicatas pagas com cartão
    - Para baixar duplicatas pagas com cheque
    - Para converter títulos em outras formas de pagamento
    - Para conciliação de recebimentos

    **Conceito de Conversão:**
    No webPosto, quando um cliente paga uma duplicata/título a receber usando
    cartão ou cheque (ao invés de dinheiro/transferência), o sistema registra
    como "recebimento convertido", mantendo o histórico da forma original e final.

    **Fluxo de Uso Essencial:**
    1. **Obtenha o Título:** Use `consultar_titulo_receber` para obter o código.
    2. **Prepare os Dados:** Monte objeto com informações do recebimento.
    3. **Registre o Recebimento:** Chame `receber_titulo_convertido`.

    **Parâmetros (via objeto `dados`):**
    - `tituloReceberCodigo` (int, obrigatório): Código do título a receber.
      Obter via: `consultar_titulo_receber`
    - `valorRecebido` (float, obrigatório): Valor recebido.
      Pode ser parcial (menor que saldo) ou total.
    - `dataRecebimento` (str, obrigatório): Data do recebimento (YYYY-MM-DD).
      Exemplo: "2025-01-10"
    - `formaPagamento` (str, obrigatório): Forma de pagamento da conversão.
      Valores: "CARTAO", "CHEQUE", "PIX", "TRANSFERENCIA"
    - `contaCodigo` (int, opcional): Código da conta bancária.
      Obter via: `consultar_conta`
    - `observacao` (str, opcional): Observações sobre o recebimento.

    **Exemplo de Uso (Python):**
    ```python
    # Cenário 1: Receber duplicata paga com cartão
    receber_titulo_convertido(
        dados={
            "tituloReceberCodigo": 12345,
            "valorRecebido": 500.00,
            "dataRecebimento": "2025-01-10",
            "formaPagamento": "CARTAO",
            "observacao": "Pago com cartão Visa"
        }
    )

    # Cenário 2: Receber duplicata paga com cheque
    receber_titulo_convertido(
        dados={
            "tituloReceberCodigo": 12346,
            "valorRecebido": 1000.00,
            "dataRecebimento": "2025-01-10",
            "formaPagamento": "CHEQUE",
            "contaCodigo": 1,
            "observacao": "Cheque pré-datado para 2025-01-20"
        }
    )

    # Cenário 3: Recebimento parcial com PIX
    receber_titulo_convertido(
        dados={
            "tituloReceberCodigo": 12347,
            "valorRecebido": 250.00,  # Parcial de R$ 500
            "dataRecebimento": "2025-01-10",
            "formaPagamento": "PIX",
            "contaCodigo": 1,
            "observacao": "Pagamento parcial - saldo restante R$ 250"
        }
    )
    ```

    **Dependências:**
    - Requer: `consultar_titulo_receber` (para obter tituloReceberCodigo)
    - Opcional: `consultar_conta` (para obter contaCodigo)

    **Tools Relacionadas:**
    - `consultar_titulo_receber` - Consultar títulos a receber
    - `receber_titulo_cartao` - Receber especificamente com cartão
    - `consultar_duplicata` - Consultar duplicatas

    **Diferença entre receber_titulo_convertido e receber_titulo_cartao:**
    - `receber_titulo_convertido`: Genérico, aceita várias formas (cartão, cheque, PIX)
    - `receber_titulo_cartao`: Específico para cartões, com mais detalhes da transação

    **Nota:**
    Para recebimentos em dinheiro/transferência direta, use a tool padrão de
    baixa de títulos (sem conversão).
    """
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
    """
    **Reajusta estoque de produto combustível.**

    Esta tool permite ajustar manualmente o estoque de produtos combustíveis (gasolina,
    diesel, etanol, etc.). É específica para combustíveis e considera tanques.

    **Quando usar:**
    - Para ajustar estoque após medição de tanques
    - Para correções de estoque de combustíveis
    - Para lançar perdas ou ganhos

    **Parâmetros (via objeto `dados`):**
    - `produtoCodigo` (int): Código do produto combustível
    - `tanqueCodigo` (int): Código do tanque
    - `quantidadeAjuste` (float): Quantidade a ajustar (positivo ou negativo)
    - `dataAjuste` (str): Data do ajuste (YYYY-MM-DD)
    - `motivo` (str): Motivo do ajuste

    **Exemplo:**
    ```python
    reajustar_estoque_produto_combustivel(
        dados={
            "produtoCodigo": 1,
            "tanqueCodigo": 1,
            "quantidadeAjuste": -50.5,  # Perda de 50.5 litros
            "dataAjuste": "2025-01-10",
            "motivo": "Evaporáção"
        }
    )
    ```

    **Dependências:**
    - `consultar_produto_combustivel` (para obter produtoCodigo)
    - `consultar_tanque` (para obter tanqueCodigo)
    """
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
    """
    **Altera dados cadastrais de um cliente existente.**

    Esta tool permite atualizar informações de clientes já cadastrados no sistema,
    como endereço, telefone, email, observações, etc.

    **Quando usar:**
    - Para atualizar dados cadastrais de clientes
    - Para correção de informações
    - Para manutenção de cadastro
    - Para sincronização com sistemas externos

    **Fluxo de Uso Essencial:**
    1. **Obtenha o ID do Cliente:** Use `consultar_cliente` para obter o código.
    2. **Prepare os Dados:** Monte objeto apenas com campos a alterar.
    3. **Atualize:** Chame `alterar_cliente` com ID e dados.

    **Parâmetros:**
    - `id` (str, obrigatório): Código do cliente a ser alterado.
      Obter via: `consultar_cliente`
      Exemplo: "123"
    - `dados` (Dict, obrigatório): Objeto com campos a alterar.
      Campos possíveis:
      * `nome` (str): Nome/Razão social
      * `telefone` (str): Telefone
      * `email` (str): E-mail
      * `endereco` (str): Endereço
      * `bairro` (str): Bairro
      * `cidade` (str): Cidade
      * `estado` (str): UF
      * `cep` (str): CEP
      * `observacao` (str): Observações

    **Exemplo de Uso (Python):**
    ```python
    # Cenário 1: Atualizar telefone e email
    alterar_cliente(
        id="123",
        dados={
            "telefone": "11999998888",
            "email": "novoemail@exemplo.com"
        }
    )

    # Cenário 2: Atualizar endereço completo
    alterar_cliente(
        id="456",
        dados={
            "endereco": "Rua Nova, 456",
            "bairro": "Jardim Exemplo",
            "cidade": "São Paulo",
            "estado": "SP",
            "cep": "01234567"
        }
    )
    ```

    **Dependências:**
    - Requer: `consultar_cliente` (para obter ID do cliente)

    **Tools Relacionadas:**
    - `consultar_cliente` - Consultar clientes
    - `incluir_cliente` - Cadastrar novo cliente

    **Nota:**
    Apenas os campos enviados no objeto `dados` serão alterados.
    Campos não informados permanecem inalterados.
    """
    endpoint = f"/INTEGRACAO/CLIENTE/{id}"
    params = {}

    result = client.put(endpoint, data=dados, params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return f"Operação realizada com sucesso.\n{format_response(result.get('data', {}))}"


@mcp.tool()
def alterar_produto(id: str, dados: Dict[str, Any], empresa_codigo: Optional[int] = None) -> str:
    """
    **Altera dados cadastrais de um produto existente.**

    Esta tool permite atualizar informações de produtos já cadastrados, como descrição,
    preços, grupo, unidade de medida, etc.

    **Quando usar:**
    - Para atualizar descrição de produtos
    - Para alterar grupo ou categoria
    - Para correção de informações cadastrais
    - Para manutenção de catálogo

    **Arquitetura Multi-Tenant:**
    Alterações no produto afetam o cadastro global (nível rede). Para alterar
    preços ou estoques específicos de uma unidade, use `reajustar_produto` ou
    outras tools específicas.

    **Fluxo de Uso Essencial:**
    1. **Obtenha o ID do Produto:** Use `consultar_produto` para obter o código.
    2. **Prepare os Dados:** Monte objeto apenas com campos a alterar.
    3. **Atualize:** Chame `alterar_produto` com ID e dados.

    **Parâmetros:**
    - `id` (str, obrigatório): Código do produto a ser alterado.
      Obter via: `consultar_produto`
      Exemplo: "123"
    - `dados` (Dict, obrigatório): Objeto com campos a alterar.
      Campos possíveis:
      * `descricao` (str): Descrição do produto
      * `grupoCodigo` (int): Código do grupo
      * `unidadeMedida` (str): Unidade (UN, LT, KG, etc.)
      * `codigoBarras` (str): Código de barras
      * `observacao` (str): Observações
    - `empresa_codigo` (int, opcional): Código da empresa (contexto).
      Exemplo: 7

    **Exemplo de Uso (Python):**
    ```python
    # Cenário 1: Atualizar descrição
    alterar_produto(
        id="123",
        dados={
            "descricao": "Gasolina Comum - Nova Descrição"
        },
        empresa_codigo=7
    )

    # Cenário 2: Alterar grupo do produto
    alterar_produto(
        id="456",
        dados={
            "grupoCodigo": 5,
            "observacao": "Reclassificado em 2025-01-12"
        }
    )
    ```

    **Dependências:**
    - Requer: `consultar_produto` (para obter ID do produto)

    **Tools Relacionadas:**
    - `consultar_produto` - Consultar produtos
    - `incluir_produto` - Cadastrar novo produto
    - `reajustar_produto` - Reajustar preços

    **Nota Importante:**
    Para alterar preços específicos de uma unidade, use `reajustar_produto`.
    Esta tool altera apenas dados cadastrais gerais do produto.
    """
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
    """
    **Consulta transferências bancárias.**

    Esta tool retorna transferências bancárias registradas no sistema.

    **Parâmetros:**
    - `data_inicial` (str, obrigatório): Data inicial (YYYY-MM-DD)
    - `data_final` (str, obrigatório): Data final (YYYY-MM-DD)
    - `empresa_codigo` (int, opcional): Código da empresa
    - `conta_codigo` (int, opcional): Código da conta bancária
    - `venda_codigo` (int, opcional): Código da venda relacionada

    **Exemplo:**
    ```python
    transferencias = consultar_transferencia_bancaria(
        data_inicial="2025-01-01",
        data_final="2025-01-31",
        empresa_codigo=7
    )
    ```
    """
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
    """
    **Cria uma transferência bancária.**

    Registra transferência entre contas bancárias.

    **Parâmetros (via `dados`):**
    - `contaOrigemCodigo` (int): Conta de origem
    - `contaDestinoCodigo` (int): Conta de destino
    - `valor` (float): Valor da transferência
    - `dataTransferencia` (str): Data (YYYY-MM-DD)

    **Exemplo:**
    ```python
    incluir_transferencia(dados={"contaOrigemCodigo": 1, "contaDestinoCodigo": 2, "valor": 1000.00, "dataTransferencia": "2025-01-10"})
    ```
    """
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
    """
    **Reajusta preços de produtos em uma unidade.**

    Esta tool permite alterar preços de venda de produtos em uma unidade específica,
    aplicando reajustes percentuais ou valores fixos. É essencial para gestão de
    preços e competição de mercado.

    **Quando usar:**
    - Para reajustar preços de produtos
    - Para aplicar reajustes percentuais em massa
    - Para atualizar preços após mudanças de custo
    - Para sincronização de preços com sistemas externos

    **Arquitetura Multi-Tenant:**
    Preços são configurados por unidade (empresa). Cada filial pode ter preços
    diferentes para os mesmos produtos. O reajuste afeta apenas a unidade
    especificada.

    **Tipos de Reajuste:**
    - **Percentual**: Aumenta/diminui preço por percentual (ex: +5%)
    - **Valor Fixo**: Define preço específico
    - **Margem**: Calcula preço baseado em margem sobre custo

    **Fluxo de Uso Essencial:**
    1. **Identifique os Produtos:** Use `consultar_produto` para obter códigos.
    2. **Prepare os Dados:** Monte objeto com produtos e reajustes.
    3. **Aplique o Reajuste:** Chame `reajustar_produto`.

    **Parâmetros (via objeto `dados`):**
    - `empresaCodigo` (int, obrigatório): Código da empresa/filial.
      Obter via: `consultar_empresa`
    - `produtos` (List[Dict], obrigatório): Lista de produtos a reajustar.
      Cada produto deve conter:
      * `produtoCodigo` (int, obrigatório): Código do produto
      * `precoVenda` (float, opcional): Novo preço de venda fixo
      * `percentualReajuste` (float, opcional): Percentual de reajuste
        Exemplo: 5.0 (aumenta 5%), -10.0 (diminui 10%)
      * `margemLucro` (float, opcional): Margem de lucro sobre custo
        Exemplo: 30.0 (30% de margem)

    **Exemplo de Uso (Python):**
    ```python
    # Cenário 1: Reajustar preço de produto específico
    reajustar_produto(
        dados={
            "empresaCodigo": 7,
            "produtos": [
                {
                    "produtoCodigo": 123,
                    "precoVenda": 5.99
                }
            ]
        }
    )

    # Cenário 2: Aplicar reajuste percentual em vários produtos
    reajustar_produto(
        dados={
            "empresaCodigo": 7,
            "produtos": [
                {"produtoCodigo": 123, "percentualReajuste": 5.0},   # +5%
                {"produtoCodigo": 456, "percentualReajuste": 5.0},   # +5%
                {"produtoCodigo": 789, "percentualReajuste": 5.0}    # +5%
            ]
        }
    )

    # Cenário 3: Reajustar por margem de lucro
    reajustar_produto(
        dados={
            "empresaCodigo": 7,
            "produtos": [
                {
                    "produtoCodigo": 123,
                    "margemLucro": 30.0  # 30% sobre o custo
                }
            ]
        }
    )

    # Cenário 4: Reajuste em massa de categoria
    # Primeiro, buscar produtos da categoria
    produtos_categoria = consultar_produto(
        grupo_codigo=5,  # Grupo de lubrificantes
        empresa_codigo=7,
        limite=100
    )
    
    # Aplicar reajuste de 10% em todos
    produtos_reajuste = [
        {"produtoCodigo": p["codigo"], "percentualReajuste": 10.0}
        for p in produtos_categoria
    ]
    
    reajustar_produto(
        dados={
            "empresaCodigo": 7,
            "produtos": produtos_reajuste
        }
    )
    ```

    **Dependências:**
    - Requer: `consultar_empresa` (para obter empresaCodigo)
    - Requer: `consultar_produto` (para obter produtoCodigo)

    **Tools Relacionadas:**
    - `consultar_produto` - Consultar produtos e preços atuais
    - `alterar_produto` - Alterar dados cadastrais do produto
    - `alterar_preco_combustivel` - Reajustar preços de combustíveis

    **Diferença entre reajustar_produto e alterar_preco_combustivel:**
    - `reajustar_produto`: Genérico, para todos os tipos de produtos
    - `alterar_preco_combustivel`: Específico para combustíveis, com regras ANP

    **Validações:**
    - Produtos devem existir e estar ativos na unidade
    - Preços devem ser maiores que zero
    - Apenas um tipo de reajuste por produto (preço fixo OU percentual OU margem)

    **Dica:**
    Para reajustes em massa, consulte os produtos primeiro, aplique a lógica
    de reajuste e envie todos de uma vez para otimizar a operação.
    """
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
    """
    **Configura comissão de produto para funcionários.**

    Esta tool permite configurar regras de comissão para produtos específicos,
    definindo percentuais ou valores fixos que funcionários receberão ao vender
    determinados produtos. É essencial para gestão de comissões.

    **Quando usar:**
    - Para configurar comissões de produtos
    - Para definir incentivos de vendas
    - Para campanhas de produtos específicos
    - Para gestão de metas e bonificações

    **Tipos de Comissão:**
    - **Percentual**: Percentual sobre o valor da venda
    - **Valor Fixo**: Valor fixo por unidade vendida
    - **Por Funcionário**: Comissão específica para funcionário
    - **Geral**: Comissão padrão para todos

    **Fluxo de Uso Essencial:**
    1. **Identifique o Produto:** Use `consultar_produto` para obter o código.
    2. **Prepare os Dados:** Monte objeto com regras de comissão.
    3. **Configure:** Chame `incluir_produto_comissao`.

    **Parâmetros (via objeto `dados`):**
    - `produtoCodigo` (int, obrigatório): Código do produto.
      Obter via: `consultar_produto`
    - `empresaCodigo` (int, obrigatório): Código da empresa/filial.
      Obter via: `consultar_empresa`
    - `tipoComissao` (str, obrigatório): Tipo de comissão.
      Valores: "PERCENTUAL", "VALOR_FIXO"
    - `valorComissao` (float, obrigatório): Valor da comissão.
      Se percentual: 5.0 (5%)
      Se fixo: 0.50 (R$ 0,50 por unidade)
    - `funcionarioCodigo` (int, opcional): Funcionário específico.
      Obter via: `consultar_funcionario`
      Se omitido, vale para todos os funcionários.
    - `dataInicio` (str, opcional): Data de início da vigência (YYYY-MM-DD).
    - `dataFim` (str, opcional): Data de fim da vigência (YYYY-MM-DD).
    - `observacao` (str, opcional): Observações sobre a comissão.

    **Exemplo de Uso (Python):**
    ```python
    # Cenário 1: Comissão percentual para todos
    incluir_produto_comissao(
        dados={
            "produtoCodigo": 123,
            "empresaCodigo": 7,
            "tipoComissao": "PERCENTUAL",
            "valorComissao": 5.0,  # 5% sobre a venda
            "observacao": "Comissão padrão de lubrificantes"
        }
    )

    # Cenário 2: Comissão fixa por unidade
    incluir_produto_comissao(
        dados={
            "produtoCodigo": 456,
            "empresaCodigo": 7,
            "tipoComissao": "VALOR_FIXO",
            "valorComissao": 0.50,  # R$ 0,50 por unidade
            "observacao": "Incentivo de venda de aditivos"
        }
    )

    # Cenário 3: Comissão específica para funcionário
    incluir_produto_comissao(
        dados={
            "produtoCodigo": 789,
            "empresaCodigo": 7,
            "funcionarioCodigo": 10,  # Funcionário específico
            "tipoComissao": "PERCENTUAL",
            "valorComissao": 10.0,  # 10% (comissão especial)
            "observacao": "Comissão especial para vendedor destaque"
        }
    )

    # Cenário 4: Campanha com período definido
    incluir_produto_comissao(
        dados={
            "produtoCodigo": 123,
            "empresaCodigo": 7,
            "tipoComissao": "PERCENTUAL",
            "valorComissao": 15.0,  # 15% durante campanha
            "dataInicio": "2025-01-10",
            "dataFim": "2025-01-31",
            "observacao": "Campanha Janeiro - Lubrificantes"
        }
    )

    # Cenário 5: Configurar comissões em massa
    # Produtos de uma categoria
    produtos = consultar_produto(
        grupo_codigo=5,  # Lubrificantes
        empresa_codigo=7
    )
    
    for produto in produtos:
        incluir_produto_comissao(
            dados={
                "produtoCodigo": produto["codigo"],
                "empresaCodigo": 7,
                "tipoComissao": "PERCENTUAL",
                "valorComissao": 5.0,
                "observacao": "Comissão padrão categoria"
            }
        )
    ```

    **Dependências:**
    - Requer: `consultar_produto` (para obter produtoCodigo)
    - Requer: `consultar_empresa` (para obter empresaCodigo)
    - Opcional: `consultar_funcionario` (para obter funcionarioCodigo)

    **Tools Relacionadas:**
    - `consultar_produto` - Consultar produtos
    - `consultar_funcionario` - Consultar funcionários
    - `consultar_venda` - Consultar vendas com comissões

    **Regras de Aplicação:**
    - Comissões específicas de funcionário têm prioridade sobre gerais
    - Comissões com período definido são aplicadas apenas na vigência
    - Produtos sem comissão configurada não geram comissão

    **Dica:**
    Use períodos definidos (`dataInicio` e `dataFim`) para campanhas temporárias,
    facilitando a gestão e evitando comissões indevidas após o período.
    """
    params = {}

    result = client.post("/INTEGRACAO/PRODUTO_COMISSAO", data=dados, params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return f"Operação realizada com sucesso.\n{format_response(result.get('data', {}))}"


@mcp.tool()
def incluir_prazo_tabela_preco_item(id: str, dados: Dict[str, Any]) -> str:
    """
    **Inclui item em tabela de preços com prazo.**
    
    Adiciona produto a uma tabela de preços específica com condições de prazo,
    permitindo preços diferenciados por forma de pagamento.
    
    **Quando usar:**
    - Configurar preços por prazo de pagamento
    - Criar promoções com condições especiais
    - Gestão de tabelas de preço
    
    **Parâmetros:**
    - `id` (str, obrigatório): ID da tabela de preços
    - `dados` (dict, obrigatório): Dados do item (produto, preço, prazo)
    
    **Exemplo:**
    ```python
    incluir_prazo_tabela_preco_item(id='123', dados={'produto_codigo': 10, 'preco': 5.50})
    ```
    
    **Tools Relacionadas:** `excluir_prazo_tabela_preco_item`, `tabela_preco_prazo`
    """
    params = {}

    result = client.post("/INTEGRACAO/PRAZO_TABELA_PRECO/{id}/ITEM", data=dados, params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return f"Operação realizada com sucesso.\n{format_response(result.get('data', {}))}"


@mcp.tool()
def pedido_compra(dados: Dict[str, Any]) -> str:
    """
    **Cria pedido de compra para fornecedor.**
    
    Registra solicitação de compra de mercadorias, iniciando o ciclo de
    aquisição e controle de estoque.
    
    **Quando usar:**
    - Solicitar compra de produtos
    - Controle de pedidos a fornecedores
    - Planejamento de estoque
    
    **Parâmetros:**
    - `dados` (dict, obrigatório): Dados do pedido (fornecedor, produtos, quantidades)
    
    **Exemplo:**
    ```python
    pedido_compra(dados={'fornecedor_codigo': 10, 'itens': [{'produto': 1, 'qtd': 100}]})
    ```
    
    **Tools Relacionadas:** `consultar_compra`, `consultar_trr_pedido`
    """
    params = {}

    result = client.post("/INTEGRACAO/PEDIDO_COMPRAS", data=dados, params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return f"Operação realizada com sucesso.\n{format_response(result.get('data', {}))}"


@mcp.tool()
def consultar_cliente(cliente_codigo_externo: Optional[str] = None, cliente_codigo: Optional[list] = None, empresa_codigo: Optional[int] = None, retorna_observacoes: Optional[bool] = None, data_hora_atualizacao: Optional[str] = None, frota: Optional[bool] = None, faturamento: Optional[bool] = None, limites_bloqueios: Optional[bool] = None, ultimo_codigo: Optional[int] = None, limite: Optional[int] = None) -> str:
    """
    **Consulta clientes cadastrados no sistema.**

    Esta tool retorna informações detalhadas de clientes (pessoas físicas e jurídicas),
    incluindo dados cadastrais, limites de crédito, bloqueios, informações de frota e
    faturamento. É essencial para gestão de relacionamento com clientes.

    **Quando usar:**
    - Para buscar dados cadastrais de clientes
    - Para verificar limites de crédito e bloqueios
    - Para consultar clientes de frota
    - Para integrações com sistemas externos
    - Para validação de clientes antes de vendas

    **Arquitetura Multi-Tenant:**
    No webPosto, clientes são compartilhados entre unidades da mesma rede, mas podem
    ter configurações específicas por unidade (limites, bloqueios, preços especiais).

    **Fluxo de Uso Essencial:**
    1. **Execute a Consulta:** Chame `consultar_cliente` com filtros desejados.
    2. **Processe os Resultados:** Use os dados retornados conforme necessidade.

    **Parâmetros:**
    - `cliente_codigo` (List[int], opcional): Lista de códigos de clientes específicos.
      Exemplo: [123, 456, 789]
    - `cliente_codigo_externo` (str, opcional): Código externo do cliente (integração).
      Exemplo: "CLI-EXT-001"
    - `empresa_codigo` (int, opcional): Filtrar clientes ativos em empresa específica.
      Obter via: `consultar_empresa`
      Exemplo: 7
    - `frota` (bool, opcional): Se True, retorna apenas clientes de frota.
      Exemplo: True
    - `faturamento` (bool, opcional): Se True, inclui dados de faturamento.
      Exemplo: True
    - `limites_bloqueios` (bool, opcional): Se True, inclui limites de crédito e bloqueios.
      Muito útil para validação de vendas.
      Exemplo: True
    - `retorna_observacoes` (bool, opcional): Se True, inclui observações cadastrais.
      Exemplo: True
    - `data_hora_atualizacao` (str, opcional): Retorna clientes atualizados após data/hora.
      Formato: "YYYY-MM-DD HH:MM:SS"
      Exemplo: "2025-01-10 08:00:00"
    - `limite` (int, opcional): Número máximo de registros (default: 100, max: 2000).
    - `ultimo_codigo` (int, opcional): Para paginação, código do último cliente retornado.

    **Retorno:**
    Lista de clientes contendo:
    - Código do cliente
    - Nome/Razão social
    - CPF/CNPJ
    - Endereço completo
    - Telefones e email
    - Tipo (PF/PJ)
    - Situação (ativo/inativo/bloqueado)
    - Limite de crédito (se solicitado)
    - Bloqueios (se solicitado)
    - Dados de frota (se cliente de frota)
    - Observações (se solicitado)

    **Exemplo de Uso (Python):**
    ```python
    # Cenário 1: Buscar cliente específico por código
    cliente = consultar_cliente(
        cliente_codigo=[123],
        limites_bloqueios=True
    )

    # Cenário 2: Listar clientes de frota
    clientes_frota = consultar_cliente(
        frota=True,
        empresa_codigo=7,
        limite=50
    )

    # Cenário 3: Validar cliente antes de venda (verificar bloqueios)
    validacao = consultar_cliente(
        cliente_codigo=[456],
        limites_bloqueios=True,
        faturamento=True
    )
    
    if validacao[0]["bloqueado"]:
        print("Cliente bloqueado! Venda não permitida.")
    elif validacao[0]["limiteDisponivel"] < valor_venda:
        print("Limite de crédito insuficiente!")

    # Cenário 4: Sincronização incremental (clientes atualizados)
    novos = consultar_cliente(
        data_hora_atualizacao="2025-01-10 00:00:00",
        limite=500
    )
    ```

    **Dependências:**
    - Opcional: `consultar_empresa` (para obter empresa_codigo)

    **Tools Relacionadas:**
    - `incluir_cliente` - Cadastrar novo cliente
    - `alterar_cliente` - Alterar dados do cliente
    - `consultar_cliente_empresa` - Relação cliente-empresa
    - `cliente_frota` - Dados específicos de frota

    **Dica de Integração:**
    Use `cliente_codigo_externo` para manter sincronização com sistemas externos,
    permitindo buscar clientes pelo código do seu sistema.
    """
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
    """
    **Cadastra um novo cliente no sistema.**

    Esta tool permite criar um novo cliente (pessoa física ou jurídica) no webPosto,
    incluindo todos os dados cadastrais necessários. O cliente criado fica disponível
    para todas as unidades da rede (multi-tenant).

    **Quando usar:**
    - Para cadastrar novos clientes
    - Para integrações com sistemas externos
    - Para importação de base de clientes
    - Para cadastro via API/automação

    **Arquitetura Multi-Tenant:**
    Cliente é criado no nível da rede e fica disponível para todas as unidades.
    Use `vincular_cliente_unidade_negocio` para ativar o cliente em unidades específicas
    com configurações próprias (limites, bloqueios, preços).

    **Fluxo de Uso Essencial:**
    1. **Prepare os Dados:** Monte o objeto com informações do cliente.
    2. **Crie o Cliente:** Chame `incluir_cliente` com os dados.
    3. **Vincule à Unidade (Opcional):** Use `vincular_cliente_unidade_negocio`.

    **Parâmetros (via objeto `dados`):**
    - `nome` (str, obrigatório): Nome completo (PF) ou Razão Social (PJ).
      Exemplo: "João da Silva" ou "Posto Exemplo LTDA"
    - `cpfCnpj` (str, obrigatório): CPF (11 dígitos) ou CNPJ (14 dígitos).
      Exemplo: "12345678901" ou "12345678000190"
    - `tipo` (str, obrigatório): Tipo do cliente.
      Valores: "F" (Física) ou "J" (Jurídica)
    - `telefone` (str, opcional): Telefone principal.
      Exemplo: "11987654321"
    - `email` (str, opcional): E-mail do cliente.
      Exemplo: "cliente@exemplo.com"
    - `endereco` (str, opcional): Endereço completo.
      Exemplo: "Rua Exemplo, 123"
    - `bairro` (str, opcional): Bairro.
    - `cidade` (str, opcional): Cidade.
    - `estado` (str, opcional): UF (2 letras).
      Exemplo: "SP"
    - `cep` (str, opcional): CEP (8 dígitos).
      Exemplo: "01234567"
    - `codigoExterno` (str, opcional): Código do cliente no sistema externo.
      Muito útil para integrações.
      Exemplo: "CLI-EXT-001"
    - `observacao` (str, opcional): Observações gerais.

    **Retorno:**
    Dados do cliente criado incluindo:
    - Código do cliente (clienteCodigo)
    - Dados cadastrais confirmados

    **Exemplo de Uso (Python):**
    ```python
    # Cenário 1: Cadastrar cliente pessoa física
    cliente_pf = incluir_cliente(
        dados={
            "nome": "João da Silva",
            "cpfCnpj": "12345678901",
            "tipo": "F",
            "telefone": "11987654321",
            "email": "joao@exemplo.com",
            "endereco": "Rua Exemplo, 123",
            "bairro": "Centro",
            "cidade": "São Paulo",
            "estado": "SP",
            "cep": "01234567"
        }
    )

    # Cenário 2: Cadastrar cliente pessoa jurídica
    cliente_pj = incluir_cliente(
        dados={
            "nome": "Transportadora Exemplo LTDA",
            "cpfCnpj": "12345678000190",
            "tipo": "J",
            "telefone": "1133334444",
            "email": "contato@transportadora.com",
            "codigoExterno": "TRANSP-001"
        }
    )

    # Cenário 3: Integração com sistema externo
    cliente_integrado = incluir_cliente(
        dados={
            "nome": "Cliente Importado",
            "cpfCnpj": "98765432100",
            "tipo": "F",
            "codigoExterno": "ERP-CLI-9876",  # Mantém referência
            "observacao": "Importado do ERP em 2025-01-12"
        }
    )
    ```

    **Dependências:**
    - Nenhuma (tool independente)

    **Tools Relacionadas:**
    - `consultar_cliente` - Consultar clientes cadastrados
    - `alterar_cliente` - Alterar dados do cliente
    - `vincular_cliente_unidade_negocio` - Vincular cliente a unidade

    **Validações Importantes:**
    - CPF/CNPJ deve ser válido e único no sistema
    - Nome é obrigatório
    - Tipo deve ser "F" ou "J"

    **Dica:**
    Use `codigoExterno` para manter sincronização com sistemas externos,
    facilitando buscas e atualizações posteriores.
    """
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
    """
    **Consulta movimentações de contas bancárias.**

    Esta tool retorna movimentações (entradas e saídas) de contas bancárias.

    **Parâmetros:**
    - `data_inicial` (str, opcional): Data inicial (YYYY-MM-DD)
    - `data_final` (str, opcional): Data final (YYYY-MM-DD)
    - `empresa_codigo` (int, opcional): Código da empresa
    - `mostra_saldo` (bool, opcional): Se True, mostra saldo

    **Exemplo:**
    ```python
    movimentos = consultar_movimento_conta(
        data_inicial="2025-01-01",
        data_final="2025-01-31",
        empresa_codigo=7,
        mostra_saldo=True
    )
    ```
    """
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
    """
    **Cria uma nova movimentação de conta bancária.**

    Esta tool permite registrar manualmente movimentações bancárias (entradas/saídas).

    **Parâmetros (via objeto `dados`):**
    - `contaCodigo` (int): Código da conta bancária
    - `dataMovimento` (str): Data da movimentação (YYYY-MM-DD)
    - `tipoMovimento` (str): "E" (Entrada) ou "S" (Saída)
    - `valor` (float): Valor da movimentação
    - `historico` (str): Descrição da movimentação

    **Exemplo:**
    ```python
    incluir_movimento_conta(
        dados={
            "contaCodigo": 1,
            "dataMovimento": "2025-01-10",
            "tipoMovimento": "E",
            "valor": 5000.00,
            "historico": "Depósito - Recebimento de cliente"
        }
    )
    ```
    """
    params = {}

    result = client.post("/INTEGRACAO/MOVIMENTO_CONTA", data=dados, params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return f"Operação realizada com sucesso.\n{format_response(result.get('data', {}))}"


@mcp.tool()
def consultar_lancamento_contabil(data_inicial: str, data_final: str, empresa_codigo: Optional[int] = None, ultimo_codigo: Optional[int] = None, limite: Optional[int] = None, lote_contabil: Optional[int] = None) -> str:
    """
    **Consulta lançamentos contábeis.**

    Esta tool retorna lançamentos contábeis registrados no sistema. É usada para
    integrações contábeis e relatórios financeiros.

    **Parâmetros:**
    - `data_inicial` (str, obrigatório): Data inicial (YYYY-MM-DD)
    - `data_final` (str, obrigatório): Data final (YYYY-MM-DD)
    - `empresa_codigo` (int, opcional): Código da empresa
    - `lote_contabil` (int, opcional): Número do lote contábil
    - `limite` (int, opcional): Número máximo de registros

    **Exemplo:**
    ```python
    lancamentos = consultar_lancamento_contabil(
        data_inicial="2025-01-01",
        data_final="2025-01-31",
        empresa_codigo=7
    )
    ```
    """
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
    """
    **Cria um novo lançamento contábil.**

    Esta tool permite criar lançamentos contábeis manualmente no sistema.

    **Parâmetros (via objeto `dados`):**
    - `dataLancamento` (str): Data do lançamento (YYYY-MM-DD)
    - `historico` (str): Histórico do lançamento
    - `valor` (float): Valor do lançamento
    - `contaDebito` (int): Código da conta de débito
    - `contaCredito` (int): Código da conta de crédito

    **Exemplo:**
    ```python
    incluir_lancamento_contabil(
        dados={
            "dataLancamento": "2025-01-10",
            "historico": "Pagamento de fornecedor",
            "valor": 5000.00,
            "contaDebito": 101,
            "contaCredito": 201
        }
    )
    ```
    """
    params = {}

    result = client.post("/INTEGRACAO/LANCAMENTO_CONTABIL", data=dados, params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return f"Operação realizada com sucesso.\n{format_response(result.get('data', {}))}"


@mcp.tool()
def incluir_produto(dados: Dict[str, Any], empresa_codigo: Optional[int] = None) -> str:
    """
    **Cria um novo produto.**

    Esta tool permite cadastrar um novo produto no sistema.

    **Parâmetros:**
    - `dados` (Dict): Objeto com dados do produto:
      * `descricao` (str): Descrição do produto
      * `codigoBarras` (str, opcional): Código de barras
      * `preco` (float): Preço de venda
      * `grupoCodigo` (int): Código do grupo
    - `empresa_codigo` (int, opcional): Código da empresa

    **Exemplo:**
    ```python
    incluir_produto(
        dados={
            "descricao": "Refrigerante 2L",
            "codigoBarras": "7891234567890",
            "preco": 8.50,
            "grupoCodigo": 10
        },
        empresa_codigo=7
    )
    ```
    """
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
    """
    **Consulta grupos de clientes cadastrados.**

    Retorna os grupos de clientes (VIP, Atacado, Varejo, etc.) para segmentação.

    **Quando usar:**
    - Para listar grupos de clientes
    - Para relatórios por segmento
    - Para filtrar clientes por grupo

    **Parâmetros:**
    - `grupo_codigo` (int, opcional): Código de um grupo específico
    - `grupo_codigo_externo` (str, opcional): Código externo
    - `limite` (int, opcional): Número máximo de registros

    **Retorno:**
    - Código do grupo
    - Descrição (VIP, Atacado, Varejo, etc.)
    - Desconto padrão
    - Prazo padrão

    **Exemplo:**
    ```python
    grupos = consultar_grupo_cliente()
    ```

    **Tools Relacionadas:**
    - `consultar_cliente` - Clientes por grupo
    """
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
    """
    **Consulta transações de cartões (crédito/débito).**

    Esta tool retorna transações de cartões de crédito e débito realizadas no posto,
    incluindo vendas, recebimentos, taxas de administradoras e status de liquidação.
    É essencial para conciliação financeira e gestão de recebíveis.

    **Quando usar:**
    - Para listar transações de cartões
    - Para conciliação com administradoras
    - Para acompanhamento de recebíveis
    - Para relatórios financeiros
    - Para auditoria de vendas

    **Tipos de Cartões:**
    - **Crédito**: Visa, Mastercard, Elo, Amex, etc.
    - **Débito**: Cartões de débito das mesmas bandeiras
    - **Vale**: Vale combustível, vale alimentação

    **Fluxo de Uso Essencial:**
    1. **Obtenha o ID da Empresa (Opcional):** Use `consultar_empresa` para filtrar.
    2. **Execute a Consulta:** Chame `consultar_cartao` com período e filtros.

    **Parâmetros Principais:**
    - `data_inicial` (str, obrigatório): Data de início no formato YYYY-MM-DD.
      Exemplo: "2025-01-10"
    - `data_final` (str, obrigatório): Data de fim no formato YYYY-MM-DD.
      Exemplo: "2025-01-10"
    - `empresa_codigo` (int, opcional): Código da empresa/filial.
      Obter via: `consultar_empresa`
      Exemplo: 7
    - `apenas_pendente` (bool, opcional): Se True, retorna apenas cartões não liquidados.
      Muito útil para gestão de recebíveis.
      Exemplo: True
    - `data_filtro` (str, opcional): Tipo de data para filtro.
      Valores: "VENDA", "RECEBIMENTO", "LIQUIDACAO"
      Default: "VENDA"
    - `turno` (int, opcional): Filtrar por turno específico.
      Obter via: `consultar_turno`
    - `venda_codigo` (List[int], opcional): Filtrar por vendas específicas.
      Obter via: `consultar_venda`
    - `data_hora_atualizacao` (str, opcional): Retorna cartões atualizados após data/hora.
      Formato: "YYYY-MM-DD HH:MM:SS"
    - `limite` (int, opcional): Número máximo de registros (default: 100, max: 2000).
    - `ultimo_codigo` (int, opcional): Para paginação.

    **Retorno:**
    Lista de transações de cartões contendo:
    - Código da transação
    - Número da venda
    - Bandeira (Visa, Master, etc.)
    - Tipo (crédito/débito)
    - Valor da transação
    - Taxa da administradora
    - Valor líquido
    - Data da venda
    - Data prevista de recebimento
    - Data de liquidação (se liquidado)
    - Status (pendente/liquidado)
    - Administradora
    - NSU/Autorização

    **Exemplo de Uso (Python):**
    ```python
    # Cenário 1: Listar cartões pendentes de liquidação
    pendentes = consultar_cartao(
        data_inicial="2025-01-01",
        data_final="2025-01-10",
        empresa_codigo=7,
        apenas_pendente=True,
        data_filtro="VENDA"
    )

    # Cenário 2: Conciliação com administradora
    cartoes_mes = consultar_cartao(
        data_inicial="2025-01-01",
        data_final="2025-01-31",
        empresa_codigo=7,
        limite=500
    )
    
    total_vendas = sum(c["valorTransacao"] for c in cartoes_mes)
    total_taxas = sum(c["taxaAdministradora"] for c in cartoes_mes)
    total_liquido = sum(c["valorLiquido"] for c in cartoes_mes)

    # Cenário 3: Relatório de recebíveis (previsão)
    import datetime
    hoje = datetime.date.today()
    proximos_30_dias = hoje + datetime.timedelta(days=30)
    
    a_receber = consultar_cartao(
        data_inicial=hoje.strftime("%Y-%m-%d"),
        data_final=proximos_30_dias.strftime("%Y-%m-%d"),
        empresa_codigo=7,
        apenas_pendente=True,
        data_filtro="RECEBIMENTO"
    )
    ```

    **Dependências:**
    - Opcional: `consultar_empresa` (para obter empresa_codigo)
    - Opcional: `consultar_venda` (para obter venda_codigo)

    **Tools Relacionadas:**
    - `incluir_cartao` - Registrar transação de cartão
    - `receber_titulo_cartao` - Liquidar recebimento de cartão
    - `consultar_administradora` - Consultar administradoras de cartões

    **Dica:**
    Use `apenas_pendente=True` com `data_filtro="RECEBIMENTO"` para gestão
    de fluxo de caixa e acompanhamento de recebíveis de cartões.
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
    """
    **Autoriza a emissão de uma Nota Fiscal Eletrônica (NFe) de saída.**
    
    Esta tool envia uma NFe para autorização junto à SEFAZ. Após a autorização,
    a nota fiscal é validada e pode ser transmitida ao destinatário.
    
    **Quando usar:**
    - Para autorizar NFe de vendas
    - Para emissão de notas fiscais eletrônicas
    - Para compliance com legislação fiscal
    - Para integrações com SEFAZ
    
    **Fluxo de Autorização:**
    1. Nota criada no sistema
    2. Validação de dados
    3. Envio para SEFAZ
    4. Aguardar retorno
    5. Processar autorização ou rejeição
    
    **Parâmetros:**
    - `nota_codigo` (str, obrigatório): Código da nota a ser autorizada.
    
    **Exemplo de Uso (Python):**
    ```python
    # Autorizar uma NFe
    resultado = autorizar_nfe(nota_codigo="12345")
    
    if resultado["autorizada"]:
        print(f"NFe autorizada! Chave: {resultado['chave']}")
    else:
        print(f"Erro: {resultado['mensagem']}")
    ```
    
    **Tools Relacionadas:**
    - `consultar_nota_manifestacao` - Consultar manifestações
    - `consultar_icms` - Configurações tributárias
    
    **Observações:**
    - Operação pode demorar alguns segundos (aguardar resposta da SEFAZ)
    - Valide todos os dados antes de autorizar
    - Em caso de rejeição, corrija os erros e tente novamente
    """
    params = {}

    result = client.post("/INTEGRACAO/AUTORIZAR_NFE_SAIDA/{notaCodigo}", data=dados, params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return f"Operação realizada com sucesso.\n{format_response(result.get('data', {}))}"


@mcp.tool()
def alterar_preco_combustivel(dados: Dict[str, Any]) -> str:
    """
    **Altera preços de combustíveis com regras ANP.**

    Esta tool permite alterar preços de combustíveis (gasolina, diesel, etanol, GNV)
    seguindo as regras da ANP e gerando registros de alteração de preços.
    É específica para postos de combustíveis.

    **Quando usar:**
    - Para alterar preços de combustíveis
    - Para registrar mudanças de preço conforme ANP
    - Para sincronizar preços com distribuidoras
    - Para atualizações automáticas de preços

    **Regras ANP:**
    O webPosto registra todas as alterações de preço de combustíveis para
    atender às exigências da ANP (Agência Nacional do Petróleo), mantendo
    histórico completo de preços.

    **Fluxo de Uso Essencial:**
    1. **Identifique os Combustíveis:** Use `consultar_produto_combustivel`.
    2. **Prepare os Dados:** Monte objeto com novos preços.
    3. **Aplique a Alteração:** Chame `alterar_preco_combustivel`.

    **Parâmetros (via objeto `dados`):**
    - `empresaCodigo` (int, obrigatório): Código da empresa/filial.
      Obter via: `consultar_empresa`
    - `dataHoraAlteracao` (str, obrigatório): Data/hora da alteração.
      Formato: "YYYY-MM-DD HH:MM:SS"
      Exemplo: "2025-01-10 08:00:00"
    - `produtos` (List[Dict], obrigatório): Lista de combustíveis a alterar.
      Cada produto deve conter:
      * `produtoCodigo` (int, obrigatório): Código do combustível
      * `precoVenda` (float, obrigatório): Novo preço de venda
    - `observacao` (str, opcional): Motivo da alteração.

    **Exemplo de Uso (Python):**
    ```python
    # Cenário 1: Alterar preço de gasolina comum
    alterar_preco_combustivel(
        dados={
            "empresaCodigo": 7,
            "dataHoraAlteracao": "2025-01-10 08:00:00",
            "produtos": [
                {
                    "produtoCodigo": 1,  # Gasolina Comum
                    "precoVenda": 5.99
                }
            ],
            "observacao": "Reajuste conforme distribuidora"
        }
    )

    # Cenário 2: Alterar preços de múltiplos combustíveis
    import datetime
    agora = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    alterar_preco_combustivel(
        dados={
            "empresaCodigo": 7,
            "dataHoraAlteracao": agora,
            "produtos": [
                {"produtoCodigo": 1, "precoVenda": 5.99},  # Gasolina Comum
                {"produtoCodigo": 2, "precoVenda": 6.29},  # Gasolina Aditivada
                {"produtoCodigo": 3, "precoVenda": 6.19},  # Etanol
                {"produtoCodigo": 4, "precoVenda": 5.89}   # Diesel S10
            ],
            "observacao": "Reajuste semanal - Janeiro 2025"
        }
    )

    # Cenário 3: Integração com sistema de preços
    # Buscar combustíveis
    combustiveis = consultar_produto_combustivel(empresa_codigo=7)
    
    # Aplicar reajuste de 3% em todos
    produtos_reajuste = [
        {
            "produtoCodigo": c["codigo"],
            "precoVenda": c["precoVenda"] * 1.03  # +3%
        }
        for c in combustiveis
    ]
    
    alterar_preco_combustivel(
        dados={
            "empresaCodigo": 7,
            "dataHoraAlteracao": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "produtos": produtos_reajuste,
            "observacao": "Reajuste automático de 3%"
        }
    )
    ```

    **Dependências:**
    - Requer: `consultar_empresa` (para obter empresaCodigo)
    - Requer: `consultar_produto_combustivel` (para obter produtoCodigo)

    **Tools Relacionadas:**
    - `consultar_produto_combustivel` - Consultar combustíveis
    - `reajustar_produto` - Reajustar produtos genéricos
    - `consultar_produto` - Consultar produtos

    **Diferença entre alterar_preco_combustivel e reajustar_produto:**
    - `alterar_preco_combustivel`: Específico para combustíveis, com regras ANP
    - `reajustar_produto`: Genérico, para todos os tipos de produtos

    **Validações:**
    - Produtos devem ser combustíveis
    - Preços devem ser maiores que zero
    - Data/hora não pode ser futura

    **Nota Importante:**
    Esta tool gera registro de alteração de preço para atender às exigências
    da ANP. Use sempre que alterar preços de combustíveis.
    """
    params = {}

    result = client.post("/INTEGRACAO/ALTERACAO_PRECO_COMBUSTIVEL", data=dados, params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return f"Operação realizada com sucesso.\n{format_response(result.get('data', {}))}"


@mcp.tool()
def pagar_titulo_pagar(dados: Dict[str, Any]) -> str:
    """
    **Registra pagamento de título a pagar (baixa de contas a pagar).**

    Esta tool permite dar baixa em títulos a pagar (boletos, notas fiscais, despesas),
    registrando o pagamento efetivo com data, valor, conta bancária e forma de pagamento.
    É essencial para gestão de contas a pagar e fluxo de caixa.

    **Quando usar:**
    - Para registrar pagamento de boletos
    - Para baixar notas fiscais de fornecedores
    - Para registrar pagamento de despesas
    - Para conciliação bancária
    - Para controle de fluxo de caixa

    **Tipos de Pagamento:**
    - **Total**: Paga o valor total do título
    - **Parcial**: Paga parte do valor (gera saldo remanescente)
    - **Com Desconto**: Paga com desconto negociado
    - **Com Juros/Multa**: Paga com acréscimos por atraso

    **Fluxo de Uso Essencial:**
    1. **Obtenha o Título:** Use `consultar_titulo_pagar` para obter o código.
    2. **Prepare os Dados:** Monte objeto com informações do pagamento.
    3. **Registre o Pagamento:** Chame `pagar_titulo_pagar`.

    **Parâmetros (via objeto `dados`):**
    - `tituloPagarCodigo` (int, obrigatório): Código do título a pagar.
      Obter via: `consultar_titulo_pagar`
    - `valorPago` (float, obrigatório): Valor efetivamente pago.
      Pode incluir juros/multa ou desconto.
    - `dataPagamento` (str, obrigatório): Data do pagamento (YYYY-MM-DD).
      Exemplo: "2025-01-10"
    - `contaCodigo` (int, obrigatório): Código da conta bancária usada.
      Obter via: `consultar_conta`
    - `formaPagamento` (str, opcional): Forma de pagamento.
      Valores: "BOLETO", "TRANSFERENCIA", "PIX", "DINHEIRO", "CHEQUE"
    - `valorDesconto` (float, opcional): Valor de desconto obtido.
      Exemplo: 50.00
    - `valorJuros` (float, opcional): Valor de juros pagos.
      Exemplo: 25.00
    - `valorMulta` (float, opcional): Valor de multa paga.
      Exemplo: 10.00
    - `observacao` (str, opcional): Observações sobre o pagamento.

    **Exemplo de Uso (Python):**
    ```python
    # Cenário 1: Pagar boleto no valor exato
    pagar_titulo_pagar(
        dados={
            "tituloPagarCodigo": 12345,
            "valorPago": 5000.00,
            "dataPagamento": "2025-01-10",
            "contaCodigo": 1,
            "formaPagamento": "BOLETO",
            "observacao": "Pagamento via internet banking"
        }
    )

    # Cenário 2: Pagar com desconto
    pagar_titulo_pagar(
        dados={
            "tituloPagarCodigo": 12346,
            "valorPago": 950.00,
            "dataPagamento": "2025-01-10",
            "contaCodigo": 1,
            "formaPagamento": "PIX",
            "valorDesconto": 50.00,  # Desconto de 5%
            "observacao": "Pagamento antecipado com desconto"
        }
    )

    # Cenário 3: Pagar em atraso com juros e multa
    pagar_titulo_pagar(
        dados={
            "tituloPagarCodigo": 12347,
            "valorPago": 1035.00,
            "dataPagamento": "2025-01-10",
            "contaCodigo": 1,
            "formaPagamento": "TRANSFERENCIA",
            "valorJuros": 25.00,   # Juros de mora
            "valorMulta": 10.00,   # Multa de 1%
            "observacao": "Pagamento em atraso - vencimento 2024-12-31"
        }
    )

    # Cenário 4: Pagamento parcial
    pagar_titulo_pagar(
        dados={
            "tituloPagarCodigo": 12348,
            "valorPago": 2500.00,  # Parcial de R$ 5000
            "dataPagamento": "2025-01-10",
            "contaCodigo": 1,
            "formaPagamento": "PIX",
            "observacao": "Pagamento parcial - saldo R$ 2500 para próximo mês"
        }
    )
    ```

    **Dependências:**
    - Requer: `consultar_titulo_pagar` (para obter tituloPagarCodigo)
    - Requer: `consultar_conta` (para obter contaCodigo)

    **Tools Relacionadas:**
    - `consultar_titulo_pagar` - Consultar títulos a pagar
    - `incluir_titulo_pagar` - Criar novo título a pagar
    - `consultar_conta` - Consultar contas bancárias

    **Validações:**
    - Título deve estar pendente (não pago)
    - Valor pago deve ser maior que zero
    - Conta bancária deve existir e estar ativa
    - Data de pagamento não pode ser futura

    **Dica:**
    Para pagamentos em lote, consulte primeiro os títulos pendentes com
    `consultar_titulo_pagar(apenas_pendente=True)` e depois processe cada um.
    """
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
    """
    **Consulta formas de pagamento usadas em vendas.**

    Retorna detalhes de pagamentos recebidos nas vendas (dinheiro, cartão, PIX, etc.).

    **Parâmetros:**
    - `data_inicial`, `data_final` (str, opcional): Período
    - `empresa_codigo` (int, opcional): Código da empresa

    **Exemplo:**
    ```python
    pagamentos = consultar_venda_forma_pagamento(data_inicial="2025-01-01", data_final="2025-01-31")
    ```
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
    """
    **Consulta vendas com detalhamento completo.**

    Esta tool retorna informações detalhadas de vendas específicas, incluindo
    itens, formas de pagamento, impostos, cliente, funcionário e documentos fiscais.
    É mais completa que `consultar_venda`, ideal para análises detalhadas.

    **Quando usar:**
    - Para obter detalhes completos de vendas específicas
    - Para auditar vendas com todos os dados
    - Para integrações que precisam de informações completas
    - Para análise de vendas individuais

    **Diferença entre consultar_venda e consultar_venda_completa:**
    - `consultar_venda`: Lista vendas com informações resumidas (rápido)
    - `consultar_venda_completa`: Detalhes completos de vendas específicas (completo)

    **Fluxo de Uso Essencial:**
    1. **Obtenha IDs das Vendas:** Use `consultar_venda` para listar vendas.
    2. **Consulte Detalhes:** Chame `consultar_venda_completa` com IDs.

    **Parâmetros:**
    - `id_list` (str, obrigatório): Lista de IDs de vendas separados por vírgula.
      Obter via: `consultar_venda`
      Exemplo: "123,456,789" ou "123"
    - `vendas_com_dfe` (bool, opcional): Se True, inclui informações de DFe.
      DFe = Documento Fiscal Eletrônico (NFe, NFCe, etc.)
      Exemplo: True

    **Retorno:**
    Lista de vendas com detalhes completos:
    - **Dados da Venda:**
      * Código da venda
      * Data/hora
      * Valor total
      * Desconto
      * Acréscimo
      * Situação
    - **Cliente:**
      * Código e nome
      * CPF/CNPJ
    - **Funcionário:**
      * Código e nome
    - **Itens da Venda:**
      * Produto
      * Quantidade
      * Preço unitário
      * Subtotal
      * Desconto
    - **Formas de Pagamento:**
      * Tipo (dinheiro, cartão, etc.)
      * Valor
      * Parcelas
    - **Impostos:**
      * ICMS, PIS, COFINS, etc.
    - **Documento Fiscal (se solicitado):**
      * Chave NFe/NFCe
      * Número
      * Série
      * XML

    **Exemplo de Uso (Python):**
    ```python
    # Cenário 1: Consultar uma venda específica
    venda_detalhada = consultar_venda_completa(
        id_list="12345",
        vendas_com_dfe=True
    )

    # Cenário 2: Consultar múltiplas vendas
    vendas_detalhadas = consultar_venda_completa(
        id_list="12345,12346,12347"
    )

    # Cenário 3: Fluxo completo - listar e detalhar
    # Primeiro, listar vendas do dia
    vendas_resumo = consultar_venda(
        data_inicial="2025-01-10",
        data_final="2025-01-10",
        empresa_codigo=7
    )
    
    # Pegar IDs das vendas
    ids = [str(v["codigo"]) for v in vendas_resumo]
    ids_str = ",".join(ids)
    
    # Consultar detalhes completos
    vendas_completas = consultar_venda_completa(
        id_list=ids_str,
        vendas_com_dfe=True
    )
    
    # Analisar detalhes
    for venda in vendas_completas:
        print(f"Venda {venda['codigo']}:")
        print(f"  Cliente: {venda['clienteNome']}")
        print(f"  Total: R$ {venda['valorTotal']:.2f}")
        print(f"  Itens: {len(venda['itens'])}")
        for item in venda['itens']:
            print(f"    - {item['produtoDescricao']}: {item['quantidade']} x R$ {item['precoUnitario']:.2f}")

    # Cenário 4: Auditar venda com documento fiscal
    venda = consultar_venda_completa(
        id_list="12345",
        vendas_com_dfe=True
    )[0]
    
    if venda.get("nfce"):
        print(f"NFCe: {venda['nfce']['numero']}")
        print(f"Chave: {venda['nfce']['chave']}")
        print(f"XML disponível: {venda['nfce'].get('xml') is not None}")
    ```

    **Dependências:**
    - Requer: `consultar_venda` (para obter IDs das vendas)

    **Tools Relacionadas:**
    - `consultar_venda` - Listar vendas (resumido)
    - `consultar_abastecimento` - Abastecimentos específicos
    - `venda_resumo` - Resumo de vendas por período

    **Limitações:**
    - Máximo de IDs por consulta: 100
    - Para mais vendas, faça múltiplas consultas

    **Dica de Performance:**
    Use `consultar_venda` para filtrar e listar vendas, depois use
    `consultar_venda_completa` apenas para as vendas que realmente precisam
    de detalhamento completo, evitando sobrecarga.
    """
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
    """
    **Consulta vínculos de usuários com empresas.**
    
    Retorna relacionamento entre usuários e unidades de negócio (multi-tenant),
    definindo quais empresas cada usuário pode acessar.
    
    **Quando usar:**
    - Configurar acessos multi-tenant
    - Gestão de permissões por unidade
    - Auditoria de acessos
    
    **Parâmetros:**
    - `ultimo_codigo`, `limite` (int, opcional): Paginação
    
    **Exemplo:**
    ```python
    vinculos = consultar_usuario_empresa(limite=100)
    ```
    
    **Tools Relacionadas:** `consultar_usuario`, `consultar_empresa`
    """
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
    """
    **Consulta usuários do sistema.**
    
    Retorna lista de usuários cadastrados com permissões e acessos ao sistema,
    essencial para gestão de segurança e controle de acesso.
    
    **Quando usar:**
    - Gestão de usuários e permissões
    - Auditoria de acessos
    - Controle de segurança
    
    **Parâmetros:**
    - `ultimo_codigo`, `limite` (int, opcional): Paginação
    
    **Exemplo:**
    ```python
    usuarios = consultar_usuario(limite=100)
    ```
    
    **Tools Relacionadas:** `consultar_usuario_empresa`, `consultar_funcionario`
    """
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
    """
    **Consulta reajustes de preços em lote.**
    
    Retorna histórico de operações de reajuste de preços realizadas em lote,
    permitindo auditoria e controle de políticas de precificação.
    
    **Quando usar:**
    - Auditoria de reajustes de preços
    - Acompanhar políticas de precificação
    - Relatórios de gestão comercial
    
    **Parâmetros:**
    - `data_inicial`, `data_final` (str, obrigatório): Período (YYYY-MM-DD)
    - `realizada` (bool, opcional): Filtrar por status de execução
    - `tipo_produto` (str, opcional): Filtrar por tipo (C=Combustível, etc.)
    
    **Exemplo:**
    ```python
    reajustes = troca_preco(data_inicial='2025-01-01', data_final='2025-01-31', realizada=True)
    ```
    
    **Tools Relacionadas:** `reajustar_produto`, `alterar_preco_combustivel`
    """
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
    """
    **Consulta tabelas de preços com prazo.**
    
    Retorna configurações de tabelas de preços diferenciados por prazo
    de pagamento (à vista, 7 dias, 15 dias, etc.).
    
    **Quando usar:**
    - Listar tabelas de preço ativas
    - Consultar políticas comerciais
    - Gestão de promoções
    
    **Parâmetros:**
    - `tabela_preco_prazo_codigo` (int, opcional): Código específico
    - `ultimo_codigo`, `limite` (int, opcional): Paginação
    
    **Exemplo:**
    ```python
    tabelas = tabela_preco_prazo(limite=50)
    ```
    
    **Tools Relacionadas:** `incluir_prazo_tabela_preco_item`, `excluir_prazo_tabela_preco_item`
    """
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
    """
    **Consulta cupons SAT (Sistema Autenticador e Transmissor).**

    Retorna cupons fiscais SAT emitidos. Usado em SP para vendas no varejo.

    **Parâmetros:**
    - `data_inicial`, `data_final` (str, obrigatórios): Período
    - `empresa_codigo` (list, opcional): Códigos das empresas

    **Exemplo:**
    ```python
    sat = consultar_sat("2025-01-01", "2025-01-31")
    ```
    """
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
    """
    **Consulta sangrias de caixa.**

    Retorna retiradas de dinheiro do caixa (sangrias) realizadas.

    **Parâmetros:**
    - `data_inicial`, `data_final` (str, opcional): Período
    - `caixa_codigo` (int, opcional): Código do caixa

    **Exemplo:**
    ```python
    sangrias = sangria_caixa(data_inicial="2025-01-10", data_final="2025-01-10")
    ```
    """
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
    """
    **Consulta relatórios personalizados configurados no sistema.**
    
    Esta tool permite acessar relatórios customizados criados pelos usuários no webPosto,
    oferecendo flexibilidade para análises específicas de cada negócio. Relatórios
    personalizados podem combinar dados de múltiplas tabelas e aplicar regras de negócio
    específicas.
    
    **Quando usar:**
    - Para acessar relatórios customizados criados no sistema
    - Para análises específicas não cobertas por relatórios padrão
    - Para dashboards gerenciais personalizados
    - Para extrair dados com regras de negócio específicas
    - Para integrações que necessitam de dados em formatos customizados
    
    **Arquitetura de Relatórios Personalizados:**
    No webPosto, relatórios personalizados são criados através de uma interface de
    configuração que permite ao usuário definir:
    - Fontes de dados (tabelas e joins)
    - Filtros e condições
    - Agrupamentos e totalizações
    - Formato de saída
    
    **Fluxo de Uso Essencial:**
    1. **Liste os Relatórios:** Chame `relatorio_pernonalizado` sem filtros para ver
       todos os relatórios disponíveis.
    2. **Identifique o Relatório:** Analise a lista e identifique o código do relatório
       desejado.
    3. **Execute o Relatório:** Chame novamente passando o código específico para obter
       os dados do relatório.
    
    **Parâmetros:**
    - `ultimo_codigo` (int, opcional): Código do último relatório retornado, para paginação.
      Exemplo: 150
    - `limite` (int, opcional): Número máximo de registros a retornar (default: 100, max: 2000).
      Exemplo: 50
    
    **Retorno:**
    Lista de relatórios personalizados contendo:
    - Código do relatório
    - Nome/Descrição
    - Tipo de relatório
    - Parâmetros configurados
    - Dados do relatório (se código específico for fornecido)
    - Data de criação/atualização
    - Usuário criador
    
    **Exemplo de Uso (Python):**
    ```python
    # Cenário 1: Listar todos os relatórios personalizados disponíveis
    relatorios = relatorio_pernonalizado(limite=100)
    print("Relatórios disponíveis:", relatorios)
    
    # Cenário 2: Acessar relatório específico
    # Supondo que o código do relatório "Vendas por Região" seja 42
    dados_relatorio = relatorio_pernonalizado(ultimo_codigo=42, limite=1)
    print("Dados do relatório:", dados_relatorio)
    
    # Cenário 3: Paginação de relatórios (listar próximos 50)
    proximos = relatorio_pernonalizado(ultimo_codigo=100, limite=50)
    
    # Cenário 4: Integração com dashboard
    # Buscar múltiplos relatórios para compor um dashboard
    dashboard_data = {}
    relatorios_ids = [10, 25, 42, 58]  # IDs dos relatórios do dashboard
    
    for rel_id in relatorios_ids:
        dados = relatorio_pernonalizado(ultimo_codigo=rel_id, limite=1)
        dashboard_data[f"relatorio_{rel_id}"] = dados
    
    print("Dashboard completo:", dashboard_data)
    ```
    
    **Dicas de Análise:**
    - **Identifique Padrões:** Relatórios personalizados frequentemente revelam padrões
      de negócio específicos da operação.
    - **Combine com Outras Tools:** Use em conjunto com `vendas_periodo` e `consultar_dre`
      para análises completas.
    - **Automatize Dashboards:** Crie rotinas que executam múltiplos relatórios
      personalizados para dashboards gerenciais.
    - **Valide Dados:** Sempre valide os dados retornados, pois relatórios personalizados
      podem ter regras de negócio complexas.
    
    **Casos de Uso Estratégicos:**
    - **Dashboard Executivo:** Combinar múltiplos relatórios personalizados para visão
      consolidada do negócio.
    - **Análise de Margens:** Relatórios customizados para análise de margens por
      produto, categoria ou região.
    - **Compliance:** Relatórios específicos para auditorias e conformidade regulatória.
    - **Análise de Tendências:** Relatórios históricos para identificação de tendências
      de vendas e consumo.
    
    **Tools Relacionadas:**
    - `vendas_periodo` - Relatório padrão de vendas
    - `consultar_dre` - Demonstrativo de Resultados
    - `consultar_relatorio_mapa` - Relatório de mapa de vendas
    - `consultar_view` - Consultas a views customizadas
    
    **Observações Importantes:**
    - Relatórios personalizados são específicos de cada instalação do webPosto.
    - A estrutura de retorno pode variar conforme a configuração do relatório.
    - Alguns relatórios podem exigir parâmetros adicionais não documentados aqui.
    - Performance pode variar conforme complexidade do relatório.
    """
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
    """
    **Consulta metas de vendas por produto.**
    
    Retorna configurações de metas comerciais definidas para produtos específicos,
    permitindo acompanhamento de desempenho e gestão de incentivos.
    
    **Quando usar:**
    - Acompanhar progresso de metas de vendas
    - Avaliar performance de produtos
    - Gestão de comissões e bonificações
    - Planejamento comercial
    
    **Parâmetros:**
    - `grupo_meta_codigo` (int, opcional): Código do grupo de metas
    - `ultimo_codigo`, `limite` (int, opcional): Paginação
    
    **Exemplo:**
    ```python
    metas = consultar_produto_meta(grupo_meta_codigo=10, limite=50)
    ```
    
    **Tools Relacionadas:** `consultar_funcionario_meta`, `consultar_grupo_meta`
    """
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
    """
    **Consulta análise de rentabilidade (LMC/LMP) por produto.**
    
    Retorna Lucro Máximo de Contribuição (LMC) e Lucro Máximo de Produção (LMP)
    para análise de rentabilidade e precificação estratégica.
    
    **Quando usar:**
    - Análise de rentabilidade por produto
    - Definição de preços estratégicos
    - Avaliação de margem de contribuição
    
    **Parâmetros:**
    - `codigo_produt_lmc` (int, opcional): Código do produto para análise
    
    **Exemplo:**
    ```python
    analise = consultar_produto_lmc_lmp(codigo_produt_lmc=100)
    ```
    
    **Tools Relacionadas:** `consultar_produto`, `consultar_lmc`
    """
    params = {}
    if codigo_produt_lmc is not None:
        params["codigoProdutLmc"] = codigo_produt_lmc
    result = client.get("/INTEGRACAO/PRODUTO_LMC_LMP", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_produto_estoque(empresa_codigo: int, data_hora: Optional[str] = None, grupo_codigo: Optional[list] = None, produto_codigo: Optional[list] = None) -> str:
    """
    **Consulta estoque de produtos.**

    Esta tool retorna o estoque atual de produtos. É essencial para controle de estoque
    e gestão de inventário.

    **Quando usar:**
    - Para consultar estoque atual de produtos
    - Para relatórios de estoque
    - Para verificação de disponibilidade
    - Para análise de giro de estoque

    **Parâmetros:**
    - `empresa_codigo` (int, obrigatório): Código da empresa.
      Obter via: `consultar_empresas`
    - `produto_codigo` (List[int], opcional): Lista de códigos de produtos específicos.
      Obter via: `consultar_produto`
    - `grupo_codigo` (List[int], opcional): Lista de códigos de grupos de produtos.
    - `data_hora` (str, opcional): Data/hora para consulta histórica (YYYY-MM-DD HH:MM:SS).

    **Retorno:**
    Lista de produtos com estoque contendo:
    - Código do produto
    - Descrição do produto
    - Quantidade em estoque
    - Estoque mínimo
    - Estoque máximo
    - Custo médio
    - Valor total do estoque
    - Última atualização

    **Exemplo de Uso (Python):**
    ```python
    # Cenário 1: Consultar estoque de todos os produtos
    estoque = consultar_produto_estoque(
        empresa_codigo=7
    )

    # Cenário 2: Consultar estoque de produtos específicos
    estoque = consultar_produto_estoque(
        empresa_codigo=7,
        produto_codigo=[123, 456, 789]
    )

    # Cenário 3: Produtos com estoque baixo
    estoque = consultar_produto_estoque(empresa_codigo=7)
    estoque_baixo = [
        p for p in estoque
        if p["quantidadeEstoque"] < p["estoqueMinimo"]
    ]
    
    for produto in estoque_baixo:
        print(f"ALERTA: {produto['descricao']} - Estoque: {produto['quantidadeEstoque']}")
    ```

    **Dependências:**
    - Requer: `consultar_empresas` (para obter empresa_codigo)
    - Opcional: `consultar_produto` (para obter produto_codigo)

    **Tools Relacionadas:**
    - `consultar_produto` - Consultar detalhes dos produtos
    - `produto_inventario` - Registrar inventário
    - `reajustar_estoque_produto_combustivel` - Ajustar estoque de combustíveis

    **Dica:**
    Use esta tool para monitoramento de estoque e alertas de reabastecimento.
    Produtos com estoque abaixo do mínimo precisam de pedido de compra.
    """
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
    """
    **Consulta produtos cadastrados no sistema.**

    Esta tool retorna informações detalhadas de produtos (combustíveis, conveniência,
    lubrificantes, etc.), incluindo códigos, descrições, grupos, preços e configurações.
    É essencial para gestão de catálogo e vendas.

    **Quando usar:**
    - Para buscar informações de produtos
    - Para listar catálogo de produtos
    - Para integrações com sistemas externos
    - Para validação de produtos antes de vendas
    - Para sincronização de preços

    **Arquitetura Multi-Tenant:**
    Produtos são cadastrados no nível da rede (compartilhados), mas cada unidade
    pode ter preços, estoques e configurações específicas via tabela
    `produto_unidade_negocio`. Use `empresa_codigo` para filtrar produtos ativos
    em uma unidade específica.

    **Tipos de Produtos no webPosto:**
    - **C**: Combustíveis (gasolina, diesel, etanol, GNV)
    - **L**: Lubrificantes (óleos, graxas)
    - **P**: Produtos de conveniência (alimentos, bebidas, acessórios)
    - **S**: Serviços (lavagem, troca de óleo)

    **Fluxo de Uso Essencial:**
    1. **Execute a Consulta:** Chame `consultar_produto` com filtros desejados.
    2. **Processe os Resultados:** Use os dados retornados conforme necessidade.

    **Parâmetros:**
    - `produto_codigo` (int, opcional): Código específico do produto.
      Exemplo: 123
    - `produto_codigo_externo` (str, opcional): Código externo (integração).
      Exemplo: "PROD-EXT-001"
    - `empresa_codigo` (int, opcional): Filtrar produtos ativos na empresa.
      Retorna apenas produtos vinculados à unidade via `produto_unidade_negocio`.
      Obter via: `consultar_empresa`
      Exemplo: 7
    - `grupo_codigo` (int, opcional): Filtrar por grupo de produtos.
      Obter via: `consultar_grupo`
      Exemplo: 5
    - `usa_produto_lmc` (bool, opcional): Filtrar produtos com LMC (Lista de Materiais de Construção).
      Exemplo: True
    - `limite` (int, opcional): Número máximo de registros (default: 100, max: 2000).
    - `ultimo_codigo` (int, opcional): Para paginação.

    **Retorno:**
    Lista de produtos contendo:
    - Código do produto
    - Descrição
    - Tipo (C/L/P/S)
    - Grupo
    - Unidade de medida
    - Código de barras
    - Situação (ativo/inativo)
    - Preços (se filtrado por empresa)
    - Estoque (se filtrado por empresa)

    **Exemplo de Uso (Python):**
    ```python
    # Cenário 1: Buscar produto específico
    produto = consultar_produto(
        produto_codigo=123,
        empresa_codigo=7
    )

    # Cenário 2: Listar todos os combustíveis
    # Nota: Filtrar por tipo requer consultar_produto_combustivel
    combustiveis = consultar_produto(
        grupo_codigo=1,  # Grupo de combustíveis
        empresa_codigo=7,
        limite=50
    )

    # Cenário 3: Buscar por código externo (integração)
    produto_ext = consultar_produto(
        produto_codigo_externo="ERP-PROD-789",
        empresa_codigo=7
    )

    # Cenário 4: Listar catálogo completo de uma unidade
    catalogo = consultar_produto(
        empresa_codigo=7,
        limite=500
    )
    ```

    **Dependências:**
    - Opcional: `consultar_empresa` (para obter empresa_codigo)
    - Opcional: `consultar_grupo` (para obter grupo_codigo)

    **Tools Relacionadas:**
    - `consultar_produto_combustivel` - Produtos combustíveis específicos
    - `consultar_produto_estoque` - Estoque de produtos
    - `incluir_produto` - Cadastrar novo produto
    - `alterar_produto` - Alterar produto
    - `reajustar_produto` - Reajustar preços

    **Diferença entre consultar_produto e consultar_produto_combustivel:**
    - `consultar_produto`: Retorna todos os tipos de produtos (genérico)
    - `consultar_produto_combustivel`: Retorna apenas combustíveis com dados específicos
      (tanque, bico, ANP, etc.)

    **Dica:**
    Para vendas, sempre filtre por `empresa_codigo` para obter preços e estoques
    corretos da unidade específica.
    """
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
    """
    **Consulta prazos de pagamento cadastrados.**

    Retorna os prazos de pagamento (30/60/90 dias, à vista, etc.) disponíveis.

    **Parâmetros:**
    - `prazo_codigo` (int, opcional): Código de um prazo específico
    - `prazo_codigo_externo` (str, opcional): Código externo

    **Retorno:**
    - Código do prazo
    - Descrição (À vista, 30 dias, 30/60 dias, etc.)
    - Número de parcelas
    - Dias entre parcelas

    **Exemplo:**
    ```python
    prazos = consultar_prazos()
    ```
    """
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
    """
    **Consulta plano de contas gerencial.**

    Retorna o plano de contas gerencial para classificação de receitas e despesas.

    **Parâmetros:**
    - `plano_conta_codigo` (int, opcional): Código específico
    - `limite` (int, opcional): Número máximo de registros

    **Retorno:**
    - Código da conta
    - Descrição
    - Tipo (receita/despesa)
    - Conta pai (hierarquia)

    **Exemplo:**
    ```python
    contas = consultar_plano_conta_gerencial()
    ```
    """
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
    """
    **Consulta plano de contas contábil.**

    Retorna o plano de contas contábil para lançamentos contábeis.

    **Parâmetros:**
    - `limite` (int, opcional): Número máximo de registros

    **Retorno:**
    - Código da conta
    - Descrição
    - Tipo (ativo, passivo, receita, despesa)
    - Nível hierárquico

    **Exemplo:**
    ```python
    contas = consultar_plano_conta_contabil()
    ```
    """
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
    """
    **Consulta placares de performance e rankings para gamificação e motivação.**
    
    Esta tool fornece dados de placares e rankings de performance, permitindo criar
    sistemas de gamificação para motivação de equipes. Placares podem incluir rankings
    de vendas, metas atingidas, produtividade e outros indicadores de performance.
    
    **Quando usar:**
    - Para criar sistemas de gamificação e motivação de equipes
    - Para exibir rankings de performance em TVs e monitores
    - Para competições de vendas entre funcionários ou filiais
    - Para acompanhamento de metas e reconhecimento de desempenho
    - Para dashboards de performance em tempo real
    - Para relatórios de produtividade
    
    **Conceito de Placares:**
    Placares são rankings dinâmicos que mostram a performance de funcionários, filiais
    ou produtos em relação a indicadores específicos. Eles promovem competição saudável
    e reconhecimento de desempenho.
    
    **Fluxo de Uso Essencial:**
    1. **Defina o Período:** Determine datas inicial e final para o placar.
    2. **Execute a Consulta:** Chame `consultar_placares` com as datas.
    3. **Exiba os Resultados:** Apresente rankings em dashboards ou TVs.
    4. **Atualize Periodicamente:** Mantenha placares atualizados para engajamento.
    
    **Parâmetros:**
    - `data_inicial` (str, obrigatório): Data de início do período do placar.
      Formato: "YYYY-MM-DD"
      Exemplo: "2025-01-01"
    
    - `data_final` (str, obrigatório): Data de fim do período do placar.
      Formato: "YYYY-MM-DD"
      Exemplo: "2025-01-31"
    
    **Retorno:**
    Placares de performance contendo:
    - Rankings de vendas por funcionário
    - Rankings de vendas por filial
    - Rankings de produtos mais vendidos
    - Metas atingidas vs não atingidas
    - Indicadores de performance (ticket médio, volume, etc)
    - Posições no ranking
    - Pontuações e badges (se configurado)
    
    **Exemplo de Uso (Python):**
    ```python
    # Cenário 1: Placar mensal de vendas
    placar_janeiro = consultar_placares(
        data_inicial="2025-01-01",
        data_final="2025-01-31"
    )
    print("Top 10 vendedores:", placar_janeiro["ranking_vendedores"][:10])
    
    # Cenário 2: Placar semanal para competição
    placar_semanal = consultar_placares(
        data_inicial="2025-01-06",
        data_final="2025-01-12"
    )
    
    # Exibir top 3
    top3 = placar_semanal["ranking_vendedores"][:3]
    for i, vendedor in enumerate(top3, 1):
        print(f"{i}º lugar: {vendedor['nome']} - R$ {vendedor['total_vendas']:,.2f}")
    
    # Cenário 3: Dashboard de gamificação em tempo real
    # Atualizar placar a cada hora
    import datetime
    
    hoje = datetime.date.today()
    inicio_mes = hoje.replace(day=1)
    
    placar_atual = consultar_placares(
        data_inicial=str(inicio_mes),
        data_final=str(hoje)
    )
    
    # Exibir em dashboard
    dashboard_gamificacao = {
        "periodo": f"{inicio_mes} a {hoje}",
        "top_vendedores": placar_atual["ranking_vendedores"][:10],
        "top_filiais": placar_atual["ranking_filiais"][:5],
        "metas_atingidas": placar_atual["metas_atingidas"]
    }
    
    # Cenário 4: Comparação de performance entre períodos
    placar_mes_atual = consultar_placares(
        data_inicial="2025-01-01",
        data_final="2025-01-31"
    )
    
    placar_mes_anterior = consultar_placares(
        data_inicial="2024-12-01",
        data_final="2024-12-31"
    )
    
    # Identificar vendedores que melhoraram posição
    for vendedor in placar_mes_atual["ranking_vendedores"]:
        pos_atual = vendedor["posicao"]
        pos_anterior = next(
            (v["posicao"] for v in placar_mes_anterior["ranking_vendedores"] 
             if v["codigo"] == vendedor["codigo"]), 
            None
        )
        if pos_anterior and pos_atual < pos_anterior:
            print(f"{vendedor['nome']} subiu {pos_anterior - pos_atual} posições!")
    ```
    
    **Dicas de Gamificação:**
    - **Atualização Frequente:** Atualize placares regularmente (diário ou hora a hora)
      para manter engajamento.
    
    - **Reconhecimento Público:** Exiba placares em locais visíveis (TVs, murais)
      para reconhecimento e motivação.
    
    - **Múltiplos Rankings:** Crie rankings por diferentes métricas (volume, ticket
      médio, satisfação) para valorizar diferentes competências.
    
    - **Metas Alcançáveis:** Defina metas desafiadoras mas alcançáveis para manter
      motivação.
    
    - **Prêmios e Reconhecimento:** Associe placares a prêmios, badges ou
      reconhecimentos para aumentar engajamento.
    
    **Casos de Uso Estratégicos:**
    - **Competições de Vendas:** Criar competições mensais ou trimestrais.
    - **Motivação de Equipes:** Usar rankings para motivar e engajar funcionários.
    - **Identificação de Talentos:** Identificar vendedores de alto desempenho.
    - **Benchmarking:** Comparar performance entre filiais.
    - **Cultura de Performance:** Criar cultura focada em resultados e melhoria contínua.
    
    **Tools Relacionadas:**
    - `produtividade_funcionario` - Análise detalhada de produtividade
    - `vendas_periodo` - Detalhamento de vendas
    - `consultar_funcionario_meta` - Metas de funcionários
    - `consultar_relatorio_mapa` - Mapa de desempenho
    
    **Observações Importantes:**
    - Placares devem ser usados para motivação positiva, não punitiva.
    - Considere criar rankings por categorias (junior, pleno, sênior) para justiça.
    - Combine métricas quantitativas (vendas) com qualitativas (satisfação do cliente).
    - Atualize placares em horários estratégicos para maximizar visibilidade.
    """
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
    """
    **Consulta configurações de PIS e COFINS para compliance tributário federal.**
    
    Esta tool fornece acesso às configurações de PIS (Programa de Integração Social) e
    COFINS (Contribuição para Financiamento da Seguridade Social) cadastradas no sistema.
    Essencial para cálculo correto de tributos federais e compliance fiscal.
    
    **Quando usar:**
    - Para consultar alíquotas de PIS e COFINS
    - Para validação de cálculos tributários federais
    - Para auditorias fiscais
    - Para apuração de impostos
    - Para compliance com legislação federal
    - Para integrações contábeis
    
    **Conceito de PIS/COFINS:**
    PIS e COFINS são contribuições federais calculadas sobre o faturamento.
    Podem ser apuradas em regime cumulativo ou não-cumulativo, com alíquotas diferentes.
    
    **Parâmetros:**
    - `ultimo_codigo` (int, opcional): Para paginação.
    - `limite` (int, opcional): Número máximo de registros (default: 100).
    
    **Retorno:**
    Configurações de PIS/COFINS contendo:
    - Alíquotas de PIS
    - Alíquotas de COFINS
    - CST (Código de Situação Tributária)
    - Regime de apuração (cumulativo/não-cumulativo)
    - Base de cálculo
    - Isenções e benefícios fiscais
    
    **Exemplo de Uso (Python):**
    ```python
    # Listar configurações de PIS/COFINS
    pis_cofins = consultar_pisconfins(limite=200)
    
    # Calcular PIS/COFINS sobre uma venda
    valor_venda = 1000.00
    config = pis_cofins[0]  # Primeira configuração
    
    pis = valor_venda * (config["aliquotaPIS"] / 100)
    cofins = valor_venda * (config["aliquotaCOFINS"] / 100)
    
    print(f"PIS: R$ {pis:.2f}")
    print(f"COFINS: R$ {cofins:.2f}")
    print(f"Total: R$ {pis + cofins:.2f}")
    ```
    
    **Tools Relacionadas:**
    - `consultar_icms` - Configurações de ICMS
    - `consultar_dre` - Análise financeira com impostos
    """
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
    """
    **Consulta TRR (Transferência de Recebimento de Recursos) de pedidos.**
    
    Retorna registros de recebimento de mercadorias vinculados a pedidos de compra,
    essencial para controle de entrada de estoque.
    
    **Quando usar:**
    - Acompanhar recebimento de pedidos
    - Controle de entrada de mercadorias
    - Validação de entregas
    
    **Parâmetros:**
    - `pedido_codigo` (int, opcional): Código do pedido
    - `data_inicial`, `data_final` (str, opcional): Período (YYYY-MM-DD)
    - `empresa_codigo` (int, opcional): Código da empresa
    
    **Exemplo:**
    ```python
    trr = consultar_trr_pedido(pedido_codigo=123, empresa_codigo=1)
    ```
    
    **Tools Relacionadas:** `pedido_compra`, `consultar_compra`
    """
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
    """
    **Consulta itens de NFS-e (Nota Fiscal de Serviço Eletrônica).**

    Retorna itens de notas fiscais de serviço.

    **Parâmetros:**
    - `data_inicial`, `data_final` (str, opcional): Período
    - `nfse_codigo` (int, opcional): Código da NFS-e

    **Exemplo:**
    ```python
    itens = consultar_nfse(data_inicial="2025-01-01", data_final="2025-01-31")
    ```
    """
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
    """
    **Consulta NFS-e (Nota Fiscal de Serviço Eletrônica).**

    Retorna notas fiscais de serviço emitidas ou recebidas.

    **Parâmetros:**
    - `data_inicial`, `data_final` (str, opcional): Período
    - `tipo_nota` (str, opcional): "E" (Entrada) ou "S" (Saída)
    - `cliente_codigo`, `fornecedor_codigo` (int, opcional): Filtros

    **Exemplo:**
    ```python
    nfse = consultar_nfse_1(data_inicial="2025-01-01", data_final="2025-01-31", tipo_nota="S")
    ```
    """
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
    """
    **Consulta itens de notas de saída.**

    Retorna itens detalhados de notas fiscais de saída.

    **Parâmetros:**
    - `data_inicial`, `data_final` (str, opcional): Período
    - `nota_codigo` (int, opcional): Código da nota

    **Exemplo:**
    ```python
    itens = consultar_nota_saida_item(nota_codigo=123)
    ```
    """
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
    """
    **Consulta manifestações de notas fiscais eletrônicas (NFe).**
    
    Esta tool permite consultar manifestações realizadas sobre notas fiscais eletrônicas
    recebidas. A manifestação é obrigatória para confirmar ou recusar o recebimento de
    mercadorias e é essencial para compliance fiscal.
    
    **Quando usar:**
    - Para consultar status de manifestações de NFe
    - Para auditorias de notas fiscais recebidas
    - Para compliance com SEFAZ
    - Para validação de recebimento de mercadorias
    - Para integrações contábeis
    
    **Tipos de Manifestação:**
    - Confirmação da Operação
    - Ciência da Emissão
    - Desconhecimento da Operação
    - Operação Não Realizada
    
    **Parâmetros:**
    - `data_inicial`, `data_final` (str, opcional): Período de consulta.
      Formato: "YYYY-MM-DD"
    - `empresa_codigo` (int, opcional): Filtrar por empresa.
    - `compra_codigo` (int, opcional): Filtrar por compra específica.
    - `manifestacao_codigo` (int, opcional): Filtrar por manifestação específica.
    - `ultimo_codigo`, `limite` (int, opcional): Paginação.
    
    **Exemplo de Uso (Python):**
    ```python
    # Consultar manifestações do mês
    manifestacoes = consultar_nota_manifestacao(
        data_inicial="2025-01-01",
        data_final="2025-01-31",
        empresa_codigo=7
    )
    
    # Verificar manifestações pendentes
    pendentes = [m for m in manifestacoes if m["status"] == "PENDENTE"]
    print(f"Manifestações pendentes: {len(pendentes)}")
    ```
    
    **Tools Relacionadas:**
    - `autorizar_nfe` - Autorizar emissão de NFe
    - `consultar_icms` - Configurações tributárias
    """
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
    """
    **Consulta NF-e de Saída (Nota Fiscal Eletrônica).**

    Retorna NF-e de saída emitidas. Usado para vendas e transferências.

    **Parâmetros:**
    - `data_inicial`, `data_final` (str, obrigatórios): Período
    - `chave_documento` (str, opcional): Chave de acesso da NF-e
    - `situacao` (str, opcional): "A", "C", "I"

    **Exemplo:**
    ```python
    nfe = consultar_nfe_saida("2025-01-01", "2025-01-31")
    ```
    """
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
    """
    **Obtém XML de NF-e.**

    Retorna o arquivo XML de uma NF-e específica.

    **Parâmetros:**
    - `numero_documento` (int): Número da nota
    - `empresa_codigo` (int): Código da empresa
    - `serie_documento` (int): Série da nota

    **Exemplo:**
    ```python
    xml = consulta_nfe_xml(numero_documento=123, empresa_codigo=7, serie_documento=1)
    ```
    """
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
    """
    **Consulta NFC-e (Nota Fiscal de Consumidor Eletrônica).**

    Retorna NFC-e emitidas no período. Usado para vendas no varejo.

    **Parâmetros:**
    - `data_inicial`, `data_final` (str, obrigatórios): Período (YYYY-MM-DD)
    - `empresa_codigo` (list, opcional): Códigos das empresas
    - `situacao` (str, opcional): "A" (Autorizada), "C" (Cancelada)

    **Exemplo:**
    ```python
    nfce = consultar_nfce("2025-01-01", "2025-01-31", situacao="A")
    ```
    """
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
    """
    **Gera o Mapa de Desempenho consolidando vendas, custos e performance.**
    
    Esta tool fornece uma visão consolidada do desempenho operacional, combinando dados
    de vendas, custos, margens e indicadores de performance em um único relatório.
    É essencial para análise gerencial e tomada de decisões estratégicas.
    
    **Quando usar:**
    - Para análise consolidada de performance
    - Para dashboards gerenciais
    - Para comparação de desempenho entre filiais
    - Para identificação de oportunidades de melhoria
    - Para relatórios executivos
    - Para acompanhamento de metas e KPIs
    
    **Fluxo de Uso Essencial:**
    1. **Obtenha IDs das Empresas:** Use `consultar_empresa` para listar filiais.
    2. **Defina o Período:** Determine datas inicial e final.
    3. **Execute o Mapa:** Chame `consultar_relatorio_mapa` com filtros desejados.
    4. **Analise Performance:** Interprete indicadores e identifique insights.
    
    **Parâmetros:**
    - `data_inicial` (str, obrigatório): Data de início.
      Formato: "YYYY-MM-DD"
      Exemplo: "2025-01-01"
    
    - `data_final` (str, obrigatório): Data de fim.
      Formato: "YYYY-MM-DD"
      Exemplo: "2025-01-31"
    
    - `empresa_codigo` (List[int], opcional): Lista de códigos das empresas.
      Obter via: `consultar_empresa`
      Exemplo: [7, 12]
    
    - `venda_codigo` (int, opcional): Filtrar por venda específica.
      Exemplo: 12345
    
    - `quitado` (bool, opcional): Filtrar por vendas quitadas/não quitadas.
      Exemplo: True
    
    - `origem` (str, opcional): Filtrar por origem da venda (PDV, APP, etc).
      Exemplo: "PDV"
    
    - `data_hora_atualizacao` (str, opcional): Filtrar registros atualizados após data/hora.
      Formato: "YYYY-MM-DD HH:MM:SS"
      Exemplo: "2025-01-10 08:00:00"
    
    - `limite` (int, opcional): Número máximo de registros (default: 100).
    - `ultimo_codigo` (int, opcional): Para paginação.
    
    **Retorno:**
    Mapa de desempenho contendo:
    - Vendas totais por período
    - Custos e margens
    - Ticket médio
    - Volume de transações
    - Performance por filial
    - Indicadores de eficiência
    - Comparações com períodos anteriores
    
    **Exemplo de Uso (Python):**
    ```python
    # Cenário 1: Mapa de desempenho mensal de uma filial
    mapa_janeiro = consultar_relatorio_mapa(
        data_inicial="2025-01-01",
        data_final="2025-01-31",
        empresa_codigo=[7]
    )
    
    # Cenário 2: Comparação de desempenho entre filiais
    mapa_consolidado = consultar_relatorio_mapa(
        data_inicial="2025-01-01",
        data_final="2025-01-31",
        empresa_codigo=[7, 12, 25]
    )
    
    # Cenário 3: Análise de vendas quitadas
    vendas_quitadas = consultar_relatorio_mapa(
        data_inicial="2025-01-01",
        data_final="2025-01-31",
        empresa_codigo=[7],
        quitado=True
    )
    ```
    
    **Dicas de Análise:**
    - Compare margens entre filiais para identificar melhores práticas
    - Analise ticket médio para avaliar estratégias de vendas
    - Monitore volume de transações para identificar tendências
    
    **Dependências:**
    - Opcional: `consultar_empresa` (para obter empresa_codigo)
    
    **Tools Relacionadas:**
    - `vendas_periodo` - Detalhamento de vendas
    - `consultar_dre` - Análise financeira completa
    - `relatorio_pernonalizado` - Relatórios customizados
    """
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
    """
    **Consulta configurações e alíquotas de ICMS para compliance tributário.**
    
    Esta tool fornece acesso às configurações de ICMS (Imposto sobre Circulação de
    Mercadorias e Serviços) cadastradas no sistema, incluindo alíquotas, CSTs, CFOPs
    e regras de tributação. Essencial para compliance fiscal e cálculo correto de impostos.
    
    **Quando usar:**
    - Para consultar alíquotas de ICMS por estado e produto
    - Para validação de cálculos tributários
    - Para auditorias fiscais
    - Para configuração de novos produtos
    - Para compliance com legislação tributária
    - Para integrações com sistemas contábeis
    
    **Parâmetros:**
    - `ultimo_codigo` (int, opcional): Para paginação.
    - `limite` (int, opcional): Número máximo de registros (default: 100).
    
    **Retorno:**
    Configurações de ICMS contendo:
    - Alíquotas por estado (UF)
    - CST (Código de Situação Tributária)
    - CFOP (Código Fiscal de Operações)
    - Base de cálculo
    - Reduções de base
    - Isenções e benefícios fiscais
    
    **Exemplo de Uso (Python):**
    ```python
    # Listar todas as configurações de ICMS
    icms_config = consultar_icms(limite=500)
    
    # Filtrar alíquota para um estado específico
    icms_sp = [i for i in icms_config if i["uf"] == "SP"]
    print(f"Alíquota ICMS SP: {icms_sp[0]['aliquota']}%")
    ```
    
    **Tools Relacionadas:**
    - `consultar_pisconfins` - Configurações de PIS/COFINS
    - `consultar_nota_manifestacao` - Manifestação de notas fiscais
    """
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
    """
    **Consulta grupos de metas comerciais.**
    
    Retorna configurações de grupos de metas que organizam objetivos comerciais
    por período, equipe ou categoria.
    
    **Quando usar:**
    - Estruturar planejamento comercial
    - Organizar metas por período
    - Gestão de campanhas de vendas
    
    **Parâmetros:**
    - `ultimo_codigo`, `limite` (int, opcional): Paginação
    
    **Exemplo:**
    ```python
    grupos = consultar_grupo_meta(limite=50)
    ```
    
    **Tools Relacionadas:** `consultar_produto_meta`, `consultar_funcionario_meta`
    """
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
    """
    **Consulta grupos de produtos.**
    
    Retorna categorização de produtos em grupos (Combustíveis, Lubrificantes,
    Conveniência, etc.) para organização e relatórios.
    
    **Quando usar:**
    - Organizar catálogo de produtos
    - Relatórios por categoria
    - Análise de mix de produtos
    
    **Parâmetros:**
    - `grupo_codigo_externo` (str, opcional): Código externo do grupo
    - `ultimo_codigo`, `limite` (int, opcional): Paginação
    
    **Exemplo:**
    ```python
    grupos = consultar_grupo(limite=50)
    ```
    
    **Tools Relacionadas:** `consultar_sub_grupo_rede`, `consultar_produto`
    """
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
    """
    **Consulta funções/cargos de funcionários.**
    
    Retorna lista de funções (Frentista, Gerente, Caixa, etc.) para
    classificação de funcionários e gestão de RH.
    
    **Quando usar:**
    - Cadastro de funcionários
    - Relatórios de RH por cargo
    - Gestão de equipes
    
    **Parâmetros:**
    - `ultimo_codigo`, `limite` (int, opcional): Paginação
    
    **Exemplo:**
    ```python
    funcoes = consultar_funcoes(limite=50)
    ```
    
    **Tools Relacionadas:** `consultar_funcionario`, `consultar_funcionario_meta`
    """
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
    """
    **Consulta metas de vendas por funcionário.**
    
    Retorna metas individuais e coletivas de funcionários para gestão de
    desempenho e incentivos comerciais.
    
    **Quando usar:**
    - Acompanhar performance de equipes
    - Gestão de comissões
    - Avaliação de desempenho individual
    
    **Parâmetros:**
    - `grupo_meta_codigo` (int, opcional): Código do grupo de metas
    - `ultimo_codigo`, `limite` (int, opcional): Paginação
    
    **Exemplo:**
    ```python
    metas_equipe = consultar_funcionario_meta(grupo_meta_codigo=5, limite=100)
    ```
    
    **Tools Relacionadas:** `consultar_produto_meta`, `consultar_funcionario`
    """
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
    """
    **Consulta fornecedores cadastrados.**

    Esta tool retorna a lista de fornecedores (empresas ou pessoas que fornecem produtos
    e serviços) cadastrados no sistema.

    **Quando usar:**
    - Para listar fornecedores
    - Para obter ID de fornecedor antes de criar títulos a pagar
    - Para buscar fornecedor por CNPJ/CPF
    - Para integrações com sistemas externos

    **Parâmetros:**
    - `fornecedor_codigo` (int, opcional): Código de um fornecedor específico.
    - `fornecedor_codigo_externo` (str, opcional): Código externo do fornecedor.
    - `cnpj_cpf` (str, opcional): CNPJ ou CPF do fornecedor.
    - `retorna_observacoes` (bool, opcional): Se True, retorna observações.
    - `data_hora_atualizacao` (str, opcional): Filtrar por data de atualização.
    - `limite` (int, opcional): Número máximo de registros (default: 100, max: 2000).
    - `ultimo_codigo` (int, opcional): Para paginação.

    **Retorno:**
    Lista de fornecedores contendo:
    - Código do fornecedor
    - Razão social / Nome
    - Nome fantasia
    - CNPJ/CPF
    - Endereço completo
    - Telefone
    - Email
    - Status (ativo/inativo)

    **Exemplo de Uso (Python):**
    ```python
    # Cenário 1: Listar todos os fornecedores
    fornecedores = consultar_fornecedor()

    # Cenário 2: Buscar fornecedor por CNPJ
    fornecedor = consultar_fornecedor(
        cnpj_cpf="12.345.678/0001-90"
    )

    # Cenário 3: Buscar fornecedor específico
    fornecedor = consultar_fornecedor(
        fornecedor_codigo=456
    )
    ```

    **Tools Relacionadas:**
    - `incluir_titulo_pagar` - Criar título a pagar para fornecedor
    - `consultar_titulo_pagar` - Consultar títulos de fornecedores
    """
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
    """
    **Consulta formas de pagamento cadastradas.**

    Retorna as formas de pagamento (dinheiro, cartão, PIX, boleto, etc.) disponíveis no sistema.

    **Quando usar:**
    - Para listar formas de pagamento aceitas
    - Para obter IDs antes de registrar vendas/recebimentos
    - Para relatórios de vendas por forma de pagamento

    **Parâmetros:**
    - `limite` (int, opcional): Número máximo de registros
    - `ultimo_codigo` (int, opcional): Para paginação

    **Retorno:**
    - Código da forma de pagamento
    - Descrição (Dinheiro, Cartão Crédito, PIX, etc.)
    - Tipo (dinheiro, cartão, cheque, etc.)
    - Status (ativo/inativo)

    **Exemplo:**
    ```python
    formas = consultar_forma_pagamento()
    for forma in formas:
        print(f"{forma['codigo']}: {forma['descricao']}")
    ```

    **Tools Relacionadas:**
    - `consultar_venda_forma_pagamento` - Vendas por forma de pagamento
    - `receber_titulo` - Usar forma de pagamento em recebimentos
    """
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
    """
    **Consulta estoque de produtos por unidade.**

    Esta tool retorna as quantidades em estoque de produtos em cada unidade/empresa,
    incluindo estoque atual, mínimo, máximo e movimentações. É essencial para
    gestão de estoque e controle de inventário.

    **Quando usar:**
    - Para consultar estoque atual de produtos
    - Para verificar níveis de estoque mínimo/máximo
    - Para relatórios de inventário
    - Para integrações com sistemas externos
    - Para planejamento de compras

    **Arquitetura Multi-Tenant:**
    Estoque é controlado por unidade (empresa). Cada filial tem seu próprio
    estoque independente. Use `empresa_codigo` para filtrar estoque de uma
    unidade específica.

    **Tipos de Estoque:**
    - **Estoque Atual**: Quantidade disponível no momento
    - **Estoque Mínimo**: Nível mínimo configurado (alerta de reposição)
    - **Estoque Máximo**: Nível máximo configurado
    - **Estoque Reservado**: Quantidade reservada para vendas/pedidos

    **Fluxo de Uso Essencial:**
    1. **Obtenha o ID da Empresa (Opcional):** Use `consultar_empresa` para filtrar.
    2. **Execute a Consulta:** Chame `estoque` com filtros desejados.

    **Parâmetros:**
    - `empresa_codigo` (int, opcional): Código da empresa/filial.
      Obter via: `consultar_empresa`
      Exemplo: 7
    - `estoque_codigo` (int, opcional): Código específico do registro de estoque.
      Exemplo: 123
    - `estoque_codigo_externo` (str, opcional): Código externo (integração).
      Exemplo: "EST-EXT-001"
    - `data_hora_atualizacao` (str, opcional): Retorna estoques atualizados após data/hora.
      Formato: "YYYY-MM-DD HH:MM:SS"
      Exemplo: "2025-01-10 08:00:00"
    - `limite` (int, opcional): Número máximo de registros (default: 100, max: 2000).
    - `ultimo_codigo` (int, opcional): Para paginação.

    **Retorno:**
    Lista de estoques contendo:
    - Código do estoque
    - Produto (código e descrição)
    - Empresa/filial
    - Quantidade atual
    - Estoque mínimo
    - Estoque máximo
    - Estoque reservado
    - Unidade de medida
    - Última atualização
    - Localização (se configurado)

    **Exemplo de Uso (Python):**
    ```python
    # Cenário 1: Consultar estoque de uma unidade
    estoque_unidade = estoque(
        empresa_codigo=7,
        limite=500
    )

    # Cenário 2: Identificar produtos com estoque baixo
    estoque_unidade = estoque(empresa_codigo=7, limite=1000)
    
    produtos_baixo_estoque = [
        e for e in estoque_unidade 
        if e["quantidadeAtual"] <= e["estoqueMinimo"]
    ]
    
    print(f"Produtos com estoque baixo: {len(produtos_baixo_estoque)}")
    for p in produtos_baixo_estoque:
        print(f"- {p['produtoDescricao']}: {p['quantidadeAtual']} (mín: {p['estoqueMinimo']})")

    # Cenário 3: Sincronização incremental (estoques atualizados)
    novos = estoque(
        empresa_codigo=7,
        data_hora_atualizacao="2025-01-10 00:00:00",
        limite=500
    )

    # Cenário 4: Relatório de valor de estoque
    estoque_unidade = estoque(empresa_codigo=7, limite=1000)
    
    # Buscar preços dos produtos
    produtos = consultar_produto(empresa_codigo=7, limite=1000)
    precos = {p["codigo"]: p["precoCusto"] for p in produtos}
    
    valor_total = sum(
        e["quantidadeAtual"] * precos.get(e["produtoCodigo"], 0)
        for e in estoque_unidade
    )
    print(f"Valor total do estoque: R$ {valor_total:,.2f}")
    ```

    **Dependências:**
    - Opcional: `consultar_empresa` (para obter empresa_codigo)
    - Opcional: `consultar_produto` (para obter detalhes dos produtos)

    **Tools Relacionadas:**
    - `consultar_produto_estoque` - Estoque de produto específico
    - `produto_inventario` - Registrar inventário/contagem
    - `consultar_contagem_estoque` - Consultar contagens de estoque
    - `reajustar_estoque_produto_combustivel` - Ajustar estoque de combustíveis

    **Diferença entre estoque e consultar_produto_estoque:**
    - `estoque`: Lista todos os estoques de uma unidade (visão geral)
    - `consultar_produto_estoque`: Estoque de produto específico com histórico

    **Dica:**
    Use `data_hora_atualizacao` para sincronização incremental com sistemas
    externos, evitando consultar todo o estoque a cada vez.
    """
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
    """
    **Consulta empresas/filiais cadastradas no sistema.**

    Esta tool retorna informações das empresas/filiais (unidades de negócio) da rede,
    incluindo códigos, razão social, CNPJ, endereço e configurações. É essencial
    para operações multi-tenant.

    **Quando usar:**
    - Para listar todas as filiais da rede
    - Para obter `empresa_codigo` para outras tools
    - Para integrações com sistemas externos
    - Para validação de unidades de negócio
    - Para relatórios consolidados

    **Arquitetura Multi-Tenant:**
    No webPosto, cada empresa/filial é uma unidade de negócio independente.
    O `empresa_codigo` (ou `empresaCodigo`) é usado em praticamente todas as
    tools para filtrar dados específicos de cada unidade.

    **Conceito de Empresa no webPosto:**
    - **Rede**: Conjunto de todas as filiais
    - **Empresa/Filial**: Unidade de negócio individual (posto)
    - **Unidade de Negócio**: Sinônimo de empresa/filial

    **Fluxo de Uso Essencial:**
    1. **Liste as Empresas:** Chame `consultar_empresa` sem filtros.
    2. **Identifique a Unidade:** Localize o `empresaCodigo` desejado.
    3. **Use em Outras Tools:** Passe o código para filtrar dados da unidade.

    **Parâmetros:**
    - `empresa_codigo_externo` (str, opcional): Código externo (integração).
      Exemplo: "FILIAL-SP-001"
    - `limite` (int, opcional): Número máximo de registros (default: 100).
    - `ultimo_codigo` (int, opcional): Para paginação.

    **Retorno:**
    Lista de empresas contendo:
    - Código da empresa (empresaCodigo)
    - Razão social
    - Nome fantasia
    - CNPJ
    - Inscrição estadual
    - Endereço completo
    - Telefones
    - Email
    - Situação (ativa/inativa)
    - Código externo (se houver)

    **Exemplo de Uso (Python):**
    ```python
    # Cenário 1: Listar todas as filiais da rede
    empresas = consultar_empresa()
    
    for empresa in empresas:
        print(f"Código: {empresa['empresaCodigo']} - {empresa['nomeFantasia']}")

    # Cenário 2: Buscar empresa específica por código externo
    filial_sp = consultar_empresa(
        empresa_codigo_externo="FILIAL-SP-001"
    )

    # Cenário 3: Obter código para usar em outras tools
    empresas = consultar_empresa()
    empresa_codigo = empresas[0]["empresaCodigo"]
    
    # Usar o código em outras consultas
    vendas = consultar_venda(
        data_inicial="2025-01-01",
        data_final="2025-01-10",
        empresa_codigo=empresa_codigo
    )
    ```

    **Dependências:**
    - Nenhuma (tool independente)

    **Tools que Requerem empresa_codigo:**
    Praticamente todas as tools de consulta e operação requerem ou aceitam
    `empresa_codigo` como parâmetro para filtrar dados por unidade:
    - `consultar_venda`
    - `consultar_produto`
    - `consultar_cliente`
    - `consultar_abastecimento`
    - `consultar_titulo_pagar`
    - `consultar_titulo_receber`
    - E muitas outras...

    **Dica Importante:**
    Sempre que uma tool aceitar `empresa_codigo`, use-o para garantir que os
    dados retornados sejam específicos da unidade desejada, respeitando o
    isolamento multi-tenant do sistema.
    """
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
    """
    **Consulta duplicatas (títulos a pagar de fornecedores).**

    Esta tool retorna duplicatas geradas a partir de notas fiscais de entrada,
    representando títulos a pagar para fornecedores. É similar a `consultar_titulo_pagar`
    mas focada especificamente em duplicatas de compras.

    **Quando usar:**
    - Para listar duplicatas de fornecedores
    - Para acompanhamento de compras a prazo
    - Para conciliação de notas fiscais
    - Para gestão de contas a pagar de compras

    **Diferença entre consultar_duplicata e consultar_titulo_pagar:**
    - `consultar_duplicata`: Específico para duplicatas de notas fiscais de entrada
    - `consultar_titulo_pagar`: Genérico, inclui todos os tipos de títulos a pagar

    **Fluxo de Uso Essencial:**
    1. **Obtenha o ID da Empresa (Opcional):** Use `consultar_empresa` para filtrar.
    2. **Execute a Consulta:** Chame `consultar_duplicata` com período e filtros.

    **Parâmetros Principais:**
    - `data_inicial` (str, opcional): Data de início no formato YYYY-MM-DD.
      Exemplo: "2025-01-10"
    - `data_final` (str, opcional): Data de fim no formato YYYY-MM-DD.
      Exemplo: "2025-01-10"
    - `empresa_codigo` (int, opcional): Código da empresa/filial.
      Obter via: `consultar_empresa`
      Exemplo: 7
    - `fornecedor_codigo` (int, opcional): Filtrar por fornecedor específico.
      Obter via: `consultar_fornecedor`
    - `nota_entrada_codigo` (int, opcional): Filtrar por nota fiscal de entrada.
      Obter via: `consultar_nota_entrada`
    - `apenas_pendente` (bool, opcional): Se True, retorna apenas duplicatas não pagas.
      Muito útil para gestão de contas a pagar.
      Exemplo: True
    - `data_filtro` (str, opcional): Tipo de data para filtro.
      Valores: "VENCIMENTO", "EMISSAO", "PAGAMENTO"
      Default: "VENCIMENTO"
    - `linha_digitavel` (str, opcional): Buscar por linha digitável de boleto.
    - `autorizado` (bool, opcional): Filtrar duplicatas autorizadas para pagamento.
    - `tipo_lancamento` (str, opcional): Tipo de lançamento.
    - `limite` (int, opcional): Número máximo de registros (default: 100, max: 2000).
    - `ultimo_codigo` (int, opcional): Para paginação.

    **Retorno:**
    Lista de duplicatas contendo:
    - Código da duplicata
    - Número do documento
    - Nota fiscal de entrada
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
    # Cenário 1: Listar duplicatas pendentes a vencer
    pendentes = consultar_duplicata(
        data_inicial="2025-01-10",
        data_final="2025-01-31",
        empresa_codigo=7,
        apenas_pendente=True,
        data_filtro="VENCIMENTO"
    )

    # Cenário 2: Listar duplicatas de fornecedor específico
    duplicatas_fornecedor = consultar_duplicata(
        fornecedor_codigo=456,
        data_inicial="2025-01-01",
        data_final="2025-01-31",
        empresa_codigo=7
    )

    # Cenário 3: Buscar duplicata por linha digitável
    duplicata = consultar_duplicata(
        linha_digitavel="34191.79001 01043.510047 91020.150008 1 96610000005000"
    )

    # Cenário 4: Relatório de duplicatas do mês
    duplicatas_mes = consultar_duplicata(
        data_inicial="2025-01-01",
        data_final="2025-01-31",
        empresa_codigo=7,
        limite=500
    )
    
    total_duplicatas = sum(d["valorOriginal"] for d in duplicatas_mes)
    total_pendente = sum(d["saldoPendente"] for d in duplicatas_mes if d["saldoPendente"] > 0)
    ```

    **Dependências:**
    - Opcional: `consultar_empresa` (para obter empresa_codigo)
    - Opcional: `consultar_fornecedor` (para obter fornecedor_codigo)
    - Opcional: `consultar_nota_entrada` (para obter nota_entrada_codigo)

    **Tools Relacionadas:**
    - `consultar_titulo_pagar` - Consultar todos os títulos a pagar
    - `pagar_titulo_pagar` - Pagar duplicata
    - `consultar_nota_entrada` - Consultar notas fiscais de entrada
    - `consultar_fornecedor` - Consultar fornecedores

    **Dica:**
    Use `apenas_pendente=True` com `data_filtro="VENCIMENTO"` para planejamento
    de fluxo de caixa e gestão de pagamentos a fornecedores.
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
    result = client.get("/INTEGRACAO/DUPLICATA", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_dre(data_inicial: str, data_final: str, apuracao_caixa: Optional[bool] = None, cfop_outras_saidas: Optional[bool] = None, apurar_juros_descontos: Optional[bool] = None, filiais: Optional[list] = None, centro_custo_codigo: Optional[list] = None, apurar_centro_custo_produto: Optional[bool] = None) -> str:
    """
    **Gera o Demonstrativo de Resultados do Exercício (DRE) para análise financeira.**
    
    Esta tool é fundamental para gestão financeira e contábil, fornecendo uma visão completa
    da performance econômica do negócio. O DRE apresenta receitas, custos, despesas e
    resultado líquido de forma estruturada, permitindo análise de rentabilidade e tomada
    de decisões estratégicas.
    
    **Quando usar:**
    - Para análise de rentabilidade do negócio
    - Para fechamento contábil mensal/anual
    - Para comparação de performance entre períodos
    - Para análise de margens de contribuição
    - Para identificação de oportunidades de redução de custos
    - Para relatórios gerenciais e executivos
    - Para compliance contábil e fiscal
    
    **Estrutura do DRE:**
    O DRE segue a estrutura contábil padrão:
    ```
    Receita Bruta
    (-) Deduções e Abatimentos
    (=) Receita Líquida
    (-) Custo das Mercadorias Vendidas (CMV)
    (=) Lucro Bruto
    (-) Despesas Operacionais
    (=) Resultado Operacional (EBITDA)
    (+/-) Resultado Financeiro
    (=) Resultado antes de Impostos
    (-) Impostos
    (=) Resultado Líquido
    ```
    
    **Fluxo de Uso Essencial:**
    1. **Obtenha IDs das Filiais:** Use `consultar_empresa` para obter códigos das filiais.
    2. **Defina o Período:** Determine as datas inicial e final para análise.
    3. **Configure Parâmetros:** Escolha o tipo de apuração (caixa ou competência).
    4. **Execute o DRE:** Chame `consultar_dre` com os parâmetros configurados.
    5. **Analise Resultados:** Interprete os indicadores e identifique insights.
    
    **Parâmetros:**
    - `data_inicial` (str, obrigatório): Data de início do período.
      Formato: "YYYY-MM-DD"
      Exemplo: "2025-01-01"
    
    - `data_final` (str, obrigatório): Data de fim do período.
      Formato: "YYYY-MM-DD"
      Exemplo: "2025-01-31"
    
    - `filiais` (List[int], opcional): Lista de códigos das filiais para incluir no DRE.
      Obter via: `consultar_empresa`
      Exemplo: [7, 12, 25]
    
    - `apuracao_caixa` (bool, opcional): Se True, usa regime de caixa; se False, competência.
      Default: False (competência)
      Exemplo: True
    
    - `cfop_outras_saidas` (bool, opcional): Se True, inclui CFOPs de outras saídas no DRE.
      Exemplo: False
    
    - `apurar_juros_descontos` (bool, opcional): Se True, separa juros e descontos no resultado.
      Exemplo: True
    
    - `centro_custo_codigo` (List[int], opcional): Filtrar por centros de custo específicos.
      Obter via: `consultar_centro_custo`
      Exemplo: [10, 20]
    
    - `apurar_centro_custo_produto` (bool, opcional): Se True, detalha por centro de custo/produto.
      Exemplo: True
    
    **Retorno:**
    DRE estruturado contendo:
    - Receita bruta total
    - Deduções (devoluções, descontos, impostos)
    - Receita líquida
    - Custo das mercadorias vendidas (CMV)
    - Lucro bruto e margem bruta (%)
    - Despesas operacionais detalhadas
    - Resultado operacional (EBITDA)
    - Resultado financeiro (juros, descontos)
    - Resultado líquido e margem líquida (%)
    - Indicadores de performance (ROI, ROE)
    
    **Exemplo de Uso (Python):**
    ```python
    # Cenário 1: DRE mensal simples (regime de competência)
    dre_janeiro = consultar_dre(
        data_inicial="2025-01-01",
        data_final="2025-01-31",
        filiais=[7],
        apuracao_caixa=False
    )
    print("DRE Janeiro:", dre_janeiro)
    
    # Cenário 2: DRE consolidado de múltiplas filiais (regime de caixa)
    dre_consolidado = consultar_dre(
        data_inicial="2025-01-01",
        data_final="2025-03-31",
        filiais=[7, 12, 25],
        apuracao_caixa=True,
        apurar_juros_descontos=True
    )
    
    # Cenário 3: DRE detalhado por centro de custo
    dre_detalhado = consultar_dre(
        data_inicial="2025-01-01",
        data_final="2025-12-31",
        filiais=[7],
        centro_custo_codigo=[10, 20, 30],
        apurar_centro_custo_produto=True
    )
    
    # Cenário 4: Comparação entre períodos
    # DRE do mês atual
    dre_atual = consultar_dre(
        data_inicial="2025-01-01",
        data_final="2025-01-31",
        filiais=[7]
    )
    
    # DRE do mês anterior
    dre_anterior = consultar_dre(
        data_inicial="2024-12-01",
        data_final="2024-12-31",
        filiais=[7]
    )
    
    # Calcular variação
    variacao_receita = (
        (dre_atual["receitaLiquida"] - dre_anterior["receitaLiquida"]) / 
        dre_anterior["receitaLiquida"] * 100
    )
    print(f"Variação de receita: {variacao_receita:.2f}%")
    ```
    
    **Dicas de Análise:**
    - **Margem Bruta:** Indica eficiência na precificação e gestão de custos.
      Ideal: > 30% para postos de combustível.
    
    - **Margem Líquida:** Mostra a rentabilidade final do negócio.
      Ideal: > 5% para o setor.
    
    - **EBITDA:** Mede a capacidade de geração de caixa operacional.
      Quanto maior, melhor a saúde financeira.
    
    - **Comparações:** Sempre compare DREs de períodos similares (mês vs mês,
      ano vs ano) para identificar tendências.
    
    - **Análise Vertical:** Calcule cada linha do DRE como % da receita líquida
      para identificar desvios.
    
    - **Análise Horizontal:** Compare DREs de períodos consecutivos para identificar
      crescimento ou redução de itens específicos.
    
    **Casos de Uso Estratégicos:**
    - **Planejamento Orçamentário:** Use DREs históricos para projetar orçamentos futuros.
    - **Análise de Viabilidade:** Avalie a viabilidade de novos investimentos ou expansões.
    - **Negociação com Fornecedores:** Use dados de CMV para negociar melhores condições.
    - **Gestão de Custos:** Identifique despesas que podem ser otimizadas ou eliminadas.
    - **Valuation:** DREs são essenciais para avaliação do valor da empresa.
    
    **Dependências:**
    - Opcional: `consultar_empresa` (para obter filiais)
    - Opcional: `consultar_centro_custo` (para filtrar por centro de custo)
    
    **Tools Relacionadas:**
    - `vendas_periodo` - Detalhamento das receitas
    - `consultar_despesa_financeiro_rede` - Análise de despesas
    - `relatorio_pernonalizado` - Relatórios customizados
    - `consultar_relatorio_mapa` - Mapa de vendas e custos
    
    **Observações Importantes:**
    - **Regime de Caixa vs Competência:** Escolha conforme necessidade contábil.
      Caixa: considera quando o dinheiro entra/sai.
      Competência: considera quando a transação ocorre.
    
    - **Performance:** DREs consolidados de múltiplas filiais podem demorar mais para processar.
    
    - **Precisão:** Garanta que todos os lançamentos contábeis estejam corretos antes
      de gerar o DRE.
    """
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
    """
    **Consulta contas bancárias cadastradas.**

    Esta tool retorna a lista de contas bancárias (contas correntes, poupança, etc.)
    cadastradas no sistema.

    **Parâmetros:**
    - `empresa_codigo` (int, opcional): Código da empresa
    - `limite` (int, opcional): Número máximo de registros
    - `ultimo_codigo` (int, opcional): Para paginação

    **Retorno:**
    Lista de contas contendo:
    - Código da conta
    - Banco
    - Agência
    - Número da conta
    - Tipo de conta
    - Saldo atual

    **Exemplo:**
    ```python
    contas = consultar_conta(empresa_codigo=7)
    ```

    **Tools Relacionadas:**
    - `consultar_movimento_conta` - Consultar movimentações
    - `incluir_movimento_conta` - Criar movimentação
    """
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
    """
    **Consulta contagens de estoque (inventários).**

    Esta tool retorna registros de contagens de estoque (inventários) realizadas,
    incluindo produtos contados, quantidades, diferenças e ajustes. É essencial
    para auditoria e controle de estoque.

    **Quando usar:**
    - Para consultar inventários realizados
    - Para auditar contagens de estoque
    - Para verificar diferenças entre físico e sistema
    - Para relatórios de inventário
    - Para conciliação de estoque

    **Processo de Inventário:**
    1. Contagem física dos produtos
    2. Registro da contagem via `produto_inventario`
    3. Sistema calcula diferenças
    4. Ajustes automáticos de estoque
    5. Consulta via `consultar_contagem_estoque`

    **Fluxo de Uso Essencial:**
    1. **Execute a Consulta:** Chame `consultar_contagem_estoque` com data.
    2. **Analise os Resultados:** Verifique diferenças e ajustes.

    **Parâmetros:**
    - `data_contagem` (str, obrigatório): Data da contagem no formato YYYY-MM-DD.
      Exemplo: "2025-01-10"
    - `contagem_referencia` (int, opcional): Código de referência da contagem.
      Usado para agrupar contagens do mesmo inventário.
    - `limite` (int, opcional): Número máximo de registros (default: 100, max: 2000).
    - `ultimo_codigo` (int, opcional): Para paginação.

    **Retorno:**
    Lista de contagens contendo:
    - Código da contagem
    - Produto (código e descrição)
    - Empresa/filial
    - Data da contagem
    - Quantidade contada
    - Quantidade sistema (antes)
    - Diferença (contada - sistema)
    - Tipo de ajuste (entrada/saída)
    - Usuário responsável
    - Observações

    **Exemplo de Uso (Python):**
    ```python
    # Cenário 1: Consultar contagens de uma data específica
    contagens = consultar_contagem_estoque(
        data_contagem="2025-01-10",
        limite=500
    )

    # Cenário 2: Analisar diferenças de inventário
    contagens = consultar_contagem_estoque(
        data_contagem="2025-01-10",
        limite=1000
    )
    
    # Produtos com diferenças
    diferencas = [
        c for c in contagens 
        if c["diferenca"] != 0
    ]
    
    print(f"Produtos com diferenças: {len(diferencas)}")
    for d in diferencas:
        tipo = "SOBRA" if d["diferenca"] > 0 else "FALTA"
        print(f"- {d['produtoDescricao']}: {tipo} de {abs(d['diferenca'])} unidades")

    # Cenário 3: Relatório de inventário mensal
    contagens = consultar_contagem_estoque(
        data_contagem="2025-01-31",  # Último dia do mês
        limite=1000
    )
    
    total_contado = sum(c["quantidadeContada"] for c in contagens)
    total_sistema = sum(c["quantidadeSistema"] for c in contagens)
    total_diferenca = total_contado - total_sistema
    
    print(f"Total contado: {total_contado}")
    print(f"Total sistema: {total_sistema}")
    print(f"Diferença: {total_diferenca}")

    # Cenário 4: Consultar inventário específico por referência
    contagens = consultar_contagem_estoque(
        data_contagem="2025-01-10",
        contagem_referencia=123,
        limite=500
    )
    ```

    **Dependências:**
    - Relacionada: `produto_inventario` (para registrar contagens)

    **Tools Relacionadas:**
    - `produto_inventario` - Registrar contagem de estoque
    - `estoque` - Consultar estoque atual
    - `consultar_produto_estoque` - Estoque de produto específico

    **Tipos de Diferenças:**
    - **Positiva (Sobra)**: Contagem > Sistema (entrada de ajuste)
    - **Negativa (Falta)**: Contagem < Sistema (saída de ajuste)
    - **Zero**: Contagem = Sistema (sem ajuste)

    **Dica de Auditoria:**
    Diferenças significativas podem indicar:
    - Erros de lançamento de vendas/compras
    - Perdas não registradas
    - Furtos ou desvios
    - Erros na contagem física
    
    Investigue diferenças acima de 5% do estoque.
    """
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
    """
    **Consulta views customizadas do banco de dados para análises avançadas.**
    
    Esta tool permite acessar views (visões) SQL customizadas criadas no banco de dados
    do webPosto. Views são consultas pré-definidas que podem combinar dados de múltiplas
    tabelas, aplicar filtros complexos e fornecer dados agregados para análises específicas.
    
    **Quando usar:**
    - Para acessar dados agregados e pré-processados
    - Para análises que requerem joins complexos
    - Para dashboards que necessitam de dados consolidados
    - Para relatórios customizados com regras de negócio específicas
    - Para consultas de performance otimizadas
    
    **Conceito de Views:**
    Views são "tabelas virtuais" que não armazenam dados, mas sim consultas SQL.
    Elas simplificam consultas complexas e garantem consistência nos dados retornados.
    
    **Fluxo de Uso Essencial:**
    1. **Identifique a View:** Determine qual view contém os dados necessários.
    2. **Configure Filtros:** Defina parâmetros como dias e volume mínimo.
    3. **Execute a Consulta:** Chame `consultar_view` com os parâmetros.
    4. **Processe Resultados:** Analise os dados retornados.
    
    **Parâmetros:**
    - `view` (str, opcional): Nome da view a ser consultada.
      Exemplos: "vw_vendas_consolidadas", "vw_estoque_critico", "vw_performance_produtos"
    
    - `dias` (int, opcional): Número de dias para filtrar dados históricos.
      Exemplo: 30 (dados dos últimos 30 dias)
    
    - `volume_minimo` (int, opcional): Volume mínimo para filtrar resultados.
      Exemplo: 1000 (apenas registros com volume >= 1000)
    
    **Retorno:**
    Dados da view consultada, que podem incluir:
    - Dados agregados (somas, médias, contagens)
    - Dados consolidados de múltiplas tabelas
    - Indicadores calculados
    - Rankings e classificações
    - Tendências e comparações
    
    **Exemplo de Uso (Python):**
    ```python
    # Cenário 1: Consultar view de vendas consolidadas dos últimos 30 dias
    vendas_consolidadas = consultar_view(
        view="vw_vendas_consolidadas",
        dias=30
    )
    
    # Cenário 2: Consultar produtos com estoque crítico
    estoque_critico = consultar_view(
        view="vw_estoque_critico",
        volume_minimo=100
    )
    
    # Cenário 3: Análise de performance de produtos
    performance = consultar_view(
        view="vw_performance_produtos",
        dias=90,
        volume_minimo=500
    )
    
    # Cenário 4: Dashboard executivo
    # Combinar múltiplas views para dashboard completo
    dashboard = {
        "vendas": consultar_view(view="vw_vendas_consolidadas", dias=30),
        "estoque": consultar_view(view="vw_estoque_critico"),
        "performance": consultar_view(view="vw_performance_produtos", dias=30)
    }
    ```
    
    **Dicas de Análise:**
    - **Identifique Views Disponíveis:** Consulte a documentação do sistema ou DBA
      para conhecer as views disponíveis.
    - **Otimize Filtros:** Use parâmetros de filtro para reduzir o volume de dados
      retornados e melhorar performance.
    - **Combine Views:** Use múltiplas views para criar análises completas.
    - **Cache Resultados:** Para dashboards, considere cachear resultados de views
      que não mudam frequentemente.
    
    **Casos de Uso Estratégicos:**
    - **Dashboard Executivo:** Combinar views de vendas, estoque e financeiro.
    - **Análise de Tendências:** Views com dados históricos agregados.
    - **Alertas Automáticos:** Views de estoque crítico, vendas baixas, etc.
    - **Relatórios Regulatórios:** Views pré-configuradas para compliance.
    
    **Tools Relacionadas:**
    - `relatorio_pernonalizado` - Relatórios customizados
    - `consultar_dre` - Análise financeira
    - `consultar_relatorio_mapa` - Mapa de desempenho
    
    **Observações Importantes:**
    - Views disponíveis variam conforme configuração do sistema.
    - Algumas views podem ter performance variável conforme volume de dados.
    - Consulte documentação específica de cada view para entender estrutura de retorno.
    """
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
    """
    **Consulta subgrupos de produtos da rede.**
    
    Retorna subcategorias de produtos compartilhadas entre unidades da rede,
    permitindo classificação hierárquica detalhada.
    
    **Quando usar:**
    - Organização hierárquica de produtos
    - Relatórios detalhados por subcategoria
    - Gestão de catálogo
    
    **Exemplo:**
    ```python
    subgrupos = consultar_sub_grupo_rede()
    ```
    
    **Tools Relacionadas:** `consultar_grupo`, `consultar_produto`
    """
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
    """
    **Consulta histórico de alterações de preços.**
    
    Retorna registro de todas as modificações de preços realizadas no sistema,
    permitindo auditoria e análise de estratégias de precificação.
    
    **Quando usar:**
    - Auditoria de preços
    - Análise de estratégias de precificação
    - Compliance e controle interno
    
    **Exemplo:**
    ```python
    historico = consultar_preco_idenfitid()
    ```
    
    **Tools Relacionadas:** `consultar_produto`, `alterar_preco_combustivel`
    """
    params = {}

    result = client.get("/INTEGRACAO/CONSULTAR_PRECO_IDENTIFID", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def consultar_lmc(data_inicial: str, data_final: str, empresa_codigo: Optional[list] = None, venda_codigo: Optional[int] = None, ultimo_codigo: Optional[int] = None, limite: Optional[int] = None, quitado: Optional[bool] = None, data_hora_atualizacao: Optional[str] = None, origem: Optional[str] = None) -> str:
    """
    **Consulta Lucro Máximo de Contribuição (LMC) por venda.**
    
    Retorna análise de rentabilidade detalhada por venda, calculando LMC
    (margem de contribuição) para avaliação de performance comercial.
    
    **Quando usar:**
    - Análise de rentabilidade por venda
    - Avaliação de margens de contribuição
    - Relatórios gerenciais de lucratividade
    
    **Parâmetros:**
    - `data_inicial`, `data_final` (str, obrigatório): Período (YYYY-MM-DD)
    - `empresa_codigo` (list, opcional): Lista de códigos de empresas
    - `quitado` (bool, opcional): Filtrar por status de pagamento
    
    **Exemplo:**
    ```python
    lmc = consultar_lmc(data_inicial='2025-01-01', data_final='2025-01-31')
    ```
    
    **Tools Relacionadas:** `consultar_lmc_1`, `consultar_produto_lmc_lmp`
    """
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
    """
    **Consulta LMC (endpoint alternativo).**
    
    Versão alternativa da consulta de Lucro Máximo de Contribuição,
    com mesma funcionalidade mas endpoint diferente.
    
    **Quando usar:**
    - Mesmos casos de uso que `consultar_lmc`
    - Usar se `consultar_lmc` apresentar problemas
    
    **Parâmetros:**
    - `data_inicial`, `data_final` (str, obrigatório): Período
    - `empresa_codigo` (list, opcional): Lista de empresas
    
    **Exemplo:**
    ```python
    lmc = consultar_lmc_1(data_inicial='2025-01-01', data_final='2025-01-31')
    ```
    
    **Tools Relacionadas:** `consultar_lmc`
    """
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
    """
    **Consulta itens de compras (produtos adquiridos).**
    
    Retorna detalhamento de produtos em notas fiscais de entrada, com
    quantidades, preços e informações fiscais.
    
    **Quando usar:**
    - Detalhar produtos de uma compra
    - Análise de preços de aquisição
    - Controle de estoque por entrada
    
    **Parâmetros:**
    - `compra_codigo` (int, opcional): Código da compra
    - `data_inicial`, `data_final` (str, opcional): Período
    - `empresa_codigo` (int, opcional): Código da empresa
    
    **Exemplo:**
    ```python
    itens = consultar_compra_item(compra_codigo=1234, empresa_codigo=1)
    ```
    
    **Tools Relacionadas:** `consultar_compra`, `consultar_produto`
    """
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
    """
    **Consulta compras de mercadorias.**
    
    Retorna notas fiscais de entrada (compras) de fornecedores, essencial para
    gestão de estoque e controle fiscal.
    
    **Quando usar:**
    - Consultar histórico de compras
    - Controle de recebimento de mercadorias
    - Auditoria fiscal de entradas
    
    **Parâmetros:**
    - `data_inicial`, `data_final` (str, opcional): Período (YYYY-MM-DD)
    - `empresa_codigo` (int, opcional): Código da empresa
    - `nota_numero`, `nota_serie` (str, opcional): Identificar nota específica
    - `situacao` (str, opcional): Filtrar por status
    
    **Exemplo:**
    ```python
    compras = consultar_compra(data_inicial='2025-01-01', data_final='2025-01-31', empresa_codigo=1)
    ```
    
    **Tools Relacionadas:** `consultar_compra_item`, `consultar_compra_xml`
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
    """
    **Consulta XML de nota fiscal de compra.**
    
    Retorna arquivo XML completo da NFe de entrada para validação fiscal
    e integrações contábeis.
    
    **Quando usar:**
    - Validação fiscal de entradas
    - Integração com sistemas contábeis
    - Auditoria de documentos fiscais
    
    **Parâmetros:**
    - `chave_nfe` (str, obrigatório): Chave de acesso da NFe (44 dígitos)
    
    **Exemplo:**
    ```python
    xml = consultar_compra_xml(chave_nfe='35250112345678901234550010000123451234567890')
    ```
    
    **Tools Relacionadas:** `consultar_compra`, `consultar_nota_entrada`
    """
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
    """
    **Consulta cheques recebidos (pré-datados e à vista).**

    Esta tool retorna cheques recebidos como forma de pagamento no posto,
    incluindo cheques à vista e pré-datados, com status de compensação,
    devolução e liquidação. É essencial para gestão de recebíveis.

    **Quando usar:**
    - Para listar cheques recebidos
    - Para acompanhamento de cheques pré-datados
    - Para controle de compensação
    - Para gestão de devoluções
    - Para relatórios financeiros

    **Status de Cheques:**
    - **Pendente**: Aguardando compensação
    - **Compensado**: Liquidado com sucesso
    - **Devolvido**: Devolvido pelo banco
    - **Cancelado**: Cancelado manualmente

    **Fluxo de Uso Essencial:**
    1. **Obtenha o ID da Empresa (Opcional):** Use `consultar_empresa` para filtrar.
    2. **Execute a Consulta:** Chame `consultar_cheque` com período e filtros.

    **Parâmetros Principais:**
    - `data_inicial` (str, obrigatório): Data de início no formato YYYY-MM-DD.
      Exemplo: "2025-01-10"
    - `data_final` (str, obrigatório): Data de fim no formato YYYY-MM-DD.
      Exemplo: "2025-01-10"
    - `empresa_codigo` (int, opcional): Código da empresa/filial.
      Obter via: `consultar_empresa`
      Exemplo: 7
    - `apenas_pendente` (bool, opcional): Se True, retorna apenas cheques não compensados.
      Muito útil para gestão de recebíveis.
      Exemplo: True
    - `data_filtro` (str, opcional): Tipo de data para filtro.
      Valores: "RECEBIMENTO", "VENCIMENTO", "COMPENSACAO"
      Default: "RECEBIMENTO"
    - `turno` (int, opcional): Filtrar por turno específico.
      Obter via: `consultar_turno`
    - `venda_codigo` (List[int], opcional): Filtrar por vendas específicas.
      Obter via: `consultar_venda`
    - `data_hora_atualizacao` (str, opcional): Retorna cheques atualizados após data/hora.
      Formato: "YYYY-MM-DD HH:MM:SS"
    - `limite` (int, opcional): Número máximo de registros (default: 100, max: 2000).
    - `ultimo_codigo` (int, opcional): Para paginação.

    **Retorno:**
    Lista de cheques contendo:
    - Código do cheque
    - Número da venda
    - Número do cheque
    - Banco
    - Agência
    - Conta
    - Cliente/Emitente
    - Valor
    - Data de recebimento
    - Data de vencimento (pré-datado)
    - Data de compensação (se compensado)
    - Status (pendente/compensado/devolvido)
    - Observações

    **Exemplo de Uso (Python):**
    ```python
    # Cenário 1: Listar cheques pré-datados a vencer
    import datetime
    hoje = datetime.date.today()
    proximos_7_dias = hoje + datetime.timedelta(days=7)
    
    a_vencer = consultar_cheque(
        data_inicial=hoje.strftime("%Y-%m-%d"),
        data_final=proximos_7_dias.strftime("%Y-%m-%d"),
        empresa_codigo=7,
        apenas_pendente=True,
        data_filtro="VENCIMENTO"
    )

    # Cenário 2: Listar cheques pendentes de compensação
    pendentes = consultar_cheque(
        data_inicial="2025-01-01",
        data_final="2025-01-31",
        empresa_codigo=7,
        apenas_pendente=True,
        data_filtro="RECEBIMENTO"
    )

    # Cenário 3: Relatório de cheques do mês
    cheques_mes = consultar_cheque(
        data_inicial="2025-01-01",
        data_final="2025-01-31",
        empresa_codigo=7,
        limite=500
    )
    
    total_cheques = sum(c["valor"] for c in cheques_mes)
    total_pendentes = sum(c["valor"] for c in cheques_mes if c["status"] == "PENDENTE")
    total_compensados = sum(c["valor"] for c in cheques_mes if c["status"] == "COMPENSADO")
    ```

    **Dependências:**
    - Opcional: `consultar_empresa` (para obter empresa_codigo)
    - Opcional: `consultar_venda` (para obter venda_codigo)

    **Tools Relacionadas:**
    - `consultar_cheque_pagar` - Cheques a pagar (emitidos)
    - `consultar_venda` - Vendas que geraram cheques

    **Dica:**
    Use `apenas_pendente=True` com `data_filtro="VENCIMENTO"` para gestão
    de cheques pré-datados e planejamento de depósitos.
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
    """
    **Consulta centros de custo cadastrados.**

    Retorna os centros de custo para classificação de despesas e receitas por departamento/área.

    **Quando usar:**
    - Para listar centros de custo
    - Para relatórios gerenciais por departamento
    - Para classificação de despesas

    **Parâmetros:**
    - `centro_custo_codigo_externo` (str, opcional): Código externo
    - `limite` (int, opcional): Número máximo de registros

    **Retorno:**
    - Código do centro de custo
    - Descrição (Administração, Vendas, Operações, etc.)
    - Status (ativo/inativo)

    **Exemplo:**
    ```python
    centros = consultar_centro_custo()
    for centro in centros:
        print(f"{centro['codigo']}: {centro['descricao']}")
    ```

    **Tools Relacionadas:**
    - `consultar_lancamento_contabil` - Lançamentos por centro de custo
    - `consultar_dre` - DRE por centro de custo
    """
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
    """
    **Consulta caixas (fechamentos de caixa).**

    Retorna informações de fechamento de caixa por período.

    **Parâmetros:**
    - `data_inicial`, `data_final` (str, obrigatórios): Período
    - `empresa_codigo` (int, opcional): Código da empresa
    - `turno` (int, opcional): Número do turno

    **Exemplo:**
    ```python
    caixas = consultar_caixa("2025-01-01", "2025-01-31")
    ```
    """
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
    """
    **Exclui título a pagar (cancelamento).**

    Esta tool permite excluir/cancelar um título a pagar que foi lançado
    incorretamente ou que não será mais pago. Use com cuidado, pois a
    exclusão é permanente.

    **Quando usar:**
    - Para cancelar títulos lançados incorretamente
    - Para excluir duplicatas de lançamentos
    - Para cancelar títulos negociados/perdoados
    - Para correção de erros de lançamento

    **Restrições:**
    - **Não pode excluir títulos já pagos**: Use estorno se necessário
    - **Exclusão é permanente**: Não há como recuperar
    - **Requer permissão**: Usuário deve ter permissão de exclusão

    **Fluxo de Uso Essencial:**
    1. **Obtenha o Título:** Use `consultar_titulo_pagar` para obter o ID.
    2. **Valide:** Confirme que o título está pendente (não pago).
    3. **Exclua:** Chame `excluir_titulo` com o ID.

    **Parâmetros:**
    - `id` (str, obrigatório): Código do título a pagar a ser excluído.
      Obter via: `consultar_titulo_pagar`
      Exemplo: "12345"

    **Exemplo de Uso (Python):**
    ```python
    # Cenário 1: Excluir título lançado incorretamente
    # Primeiro, consultar para confirmar
    titulos = consultar_titulo_pagar(
        titulo_pagar_codigo=12345
    )
    
    if titulos[0]["situacao"] == "PENDENTE":
        excluir_titulo(id="12345")
        print("Título excluído com sucesso")
    else:
        print("Não é possível excluir título já pago")

    # Cenário 2: Excluir duplicata de lançamento
    # Identificar duplicatas
    titulos = consultar_titulo_pagar(
        fornecedor_codigo=456,
        data_inicial="2025-01-01",
        data_final="2025-01-10"
    )
    
    # Verificar duplicatas pelo número do documento
    duplicatas = {}
    for t in titulos:
        doc = t["numeroDocumento"]
        if doc in duplicatas:
            # Excluir a duplicata
            excluir_titulo(id=str(t["codigo"]))
        else:
            duplicatas[doc] = t

    # Cenário 3: Cancelar título negociado
    excluir_titulo(id="12347")
    # Nota: Registre a negociação em observações antes de excluir
    ```

    **Dependências:**
    - Requer: `consultar_titulo_pagar` (para obter ID e validar)

    **Tools Relacionadas:**
    - `consultar_titulo_pagar` - Consultar títulos a pagar
    - `incluir_titulo_pagar` - Criar novo título
    - `pagar_titulo_pagar` - Pagar título

    **Alternativas:**
    - **Para títulos pagos incorretamente**: Use estorno (se disponível)
    - **Para cancelamento com histórico**: Considere marcar como cancelado
      ao invés de excluir

    **Atenção:**
    Esta operação é **irreversível**. Sempre valide o título antes de excluir
    e mantenha registro da exclusão em sistemas externos se necessário.

    **Dica de Auditoria:**
    Antes de excluir, registre as informações do título em log ou sistema
    externo para manter histórico de auditoria.
    """
    endpoint = f"/INTEGRACAO/TITULO_PAGAR/{id}"
    params = {}

    result = client.delete(endpoint, params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return "Registro excluído com sucesso."


@mcp.tool()
def excluir_prazo_tabela_preco_item(id: str) -> str:
    """
    **Exclui item de tabela de preços com prazo.**
    
    Remove produto de uma tabela de preços específica, desvinculando
    condições de preço por prazo.
    
    **Quando usar:**
    - Remover produtos de promoções
    - Limpar tabelas de preço obsoletas
    - Ajustar políticas comerciais
    
    **Parâmetros:**
    - `id` (str, obrigatório): ID do item a excluir
    
    **Exemplo:**
    ```python
    excluir_prazo_tabela_preco_item(id='456')
    ```
    
    **Tools Relacionadas:** `incluir_prazo_tabela_preco_item`, `tabela_preco_prazo`
    """
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
    """
    **Recebe título a receber com cartão (baixa específica).**

    Esta tool permite dar baixa em títulos a receber especificamente com cartão
    de crédito/débito, registrando detalhes da transação como bandeira, NSU,
    administradora e taxas. É mais específica que `receber_titulo_convertido`.

    **Quando usar:**
    - Para receber duplicatas com cartão
    - Para registrar transações de cartão em títulos
    - Para conciliação com administradoras
    - Para controle detalhado de recebíveis

    **Diferença para receber_titulo_convertido:**
    - `receber_titulo_cartao`: Específico para cartões, com detalhes da transação
    - `receber_titulo_convertido`: Genérico, aceita várias formas de pagamento

    **Fluxo de Uso Essencial:**
    1. **Obtenha o Título:** Use `consultar_titulo_receber` para obter o ID.
    2. **Prepare os Dados:** Monte objeto com detalhes da transação de cartão.
    3. **Registre o Recebimento:** Chame `receber_titulo_cartao`.

    **Parâmetros:**
    - `id` (str, obrigatório): Código do título/pedido a receber.
      Obter via: `consultar_titulo_receber` ou `consultar_pedido`
      Exemplo: "12345"
    - `dados` (Dict, obrigatório): Objeto com detalhes da transação.
      Campos:
      * `valorRecebido` (float, obrigatório): Valor recebido
      * `dataRecebimento` (str, obrigatório): Data (YYYY-MM-DD)
      * `bandeira` (str, opcional): Bandeira do cartão
        Valores: "VISA", "MASTERCARD", "ELO", "AMEX", "HIPERCARD"
      * `tipoCartao` (str, opcional): Tipo do cartão
        Valores: "CREDITO", "DEBITO"
      * `nsu` (str, opcional): NSU da transação
      * `autorizacao` (str, opcional): Código de autorização
      * `administradoraCodigo` (int, opcional): Código da administradora
      * `taxaAdministradora` (float, opcional): Taxa cobrada
      * `observacao` (str, opcional): Observações

    **Exemplo de Uso (Python):**
    ```python
    # Cenário 1: Receber título com cartão de crédito
    receber_titulo_cartao(
        id="12345",
        dados={
            "valorRecebido": 500.00,
            "dataRecebimento": "2025-01-10",
            "bandeira": "VISA",
            "tipoCartao": "CREDITO",
            "nsu": "123456789",
            "autorizacao": "ABC123",
            "administradoraCodigo": 1,
            "taxaAdministradora": 15.00,
            "observacao": "Pagamento aprovado"
        }
    )

    # Cenário 2: Receber com cartão de débito
    receber_titulo_cartao(
        id="12346",
        dados={
            "valorRecebido": 1000.00,
            "dataRecebimento": "2025-01-10",
            "bandeira": "MASTERCARD",
            "tipoCartao": "DEBITO",
            "nsu": "987654321",
            "taxaAdministradora": 10.00
        }
    )

    # Cenário 3: Recebimento parcial
    receber_titulo_cartao(
        id="12347",
        dados={
            "valorRecebido": 250.00,  # Parcial
            "dataRecebimento": "2025-01-10",
            "bandeira": "ELO",
            "tipoCartao": "CREDITO",
            "observacao": "Pagamento parcial - saldo R$ 250"
        }
    )
    ```

    **Dependências:**
    - Requer: `consultar_titulo_receber` ou `consultar_pedido` (para obter ID)
    - Opcional: `consultar_administradora` (para obter administradoraCodigo)

    **Tools Relacionadas:**
    - `consultar_titulo_receber` - Consultar títulos a receber
    - `receber_titulo_convertido` - Receber com outras formas de pagamento
    - `consultar_cartao` - Consultar transações de cartões
    - `consultar_administradora` - Consultar administradoras

    **Nota:**
    Esta tool é específica para recebimento de pedidos/títulos com cartão.
    Para recebimentos genéricos ou outras formas de pagamento, use
    `receber_titulo_convertido`.
    """
    endpoint = f"/INTEGRACAO/PEDIDO_COMBUSTIVEL/PEDIDO/{id}/RECEBER_TITULO_EM_CARTAO"
    params = {}

    result = client.put(endpoint, data=dados, params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return f"Operação realizada com sucesso.\n{format_response(result.get('data', {}))}"


@mcp.tool()
def incluir_pedido(dados: Dict[str, Any]) -> str:
    """
    **Cria novo pedido de combustível.**
    
    Registra pedido de combustível para clientes, iniciando o ciclo
    de faturamento e entrega.
    
    **Quando usar:**
    - Criar pedidos de combustível
    - Vendas para frotas
    - Gestão de pedidos B2B
    
    **Parâmetros:**
    - `dados` (dict, obrigatório): Dados do pedido (cliente, produtos, quantidades)
    
    **Exemplo:**
    ```python
    incluir_pedido(dados={'cliente_codigo': 10, 'itens': [{'produto': 1, 'qtd': 1000}]})
    ```
    
    **Tools Relacionadas:** `consultar_pedido`, `pedido_faturar`
    """
    params = {}

    result = client.post("/INTEGRACAO/PEDIDO_COMBUSTIVEL/PEDIDO", data=dados, params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return f"Operação realizada com sucesso.\n{format_response(result.get('data', {}))}"


@mcp.tool()
def pedido_faturar(id: str, dados: Dict[str, Any]) -> str:
    """
    **Fatura pedido de combustível.**
    
    Converte pedido em venda, gerando nota fiscal e registrando
    movimentação de estoque.
    
    **Quando usar:**
    - Faturar pedidos aprovados
    - Gerar NFe de pedidos
    - Finalizar ciclo de vendas B2B
    
    **Parâmetros:**
    - `id` (str, obrigatório): ID do pedido
    - `dados` (dict, obrigatório): Dados de faturamento
    
    **Exemplo:**
    ```python
    pedido_faturar(id='123', dados={'forma_pagamento': 'prazo'})
    ```
    
    **Tools Relacionadas:** `consultar_pedido`, `pedido_danfe`
    """
    params = {}

    result = client.post("/INTEGRACAO/PEDIDO_COMBUSTIVEL/PEDIDO/{id}/FATURAR", data=dados, params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return f"Operação realizada com sucesso.\n{format_response(result.get('data', {}))}"


@mcp.tool()
def pedido_danfe(id: str) -> str:
    """
    **Gera DANFE do pedido faturado.**
    
    Retorna DANFE (Documento Auxiliar da NFe) em PDF para impressão
    e entrega ao cliente.
    
    **Quando usar:**
    - Imprimir DANFE de pedidos faturados
    - Enviar comprovante fiscal ao cliente
    - Documentar entregas
    
    **Parâmetros:**
    - `id` (str, obrigatório): ID do pedido faturado
    
    **Exemplo:**
    ```python
    danfe = pedido_danfe(id='123')
    ```
    
    **Tools Relacionadas:** `pedido_faturar`, `pedido_xml`
    """
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
    """
    **Consulta pedido de combustível específico.**
    
    Retorna detalhes completos de um pedido de combustível, incluindo
    itens, status e informações fiscais.
    
    **Quando usar:**
    - Consultar detalhes de pedido específico
    - Acompanhar status de pedidos
    - Integrações com sistemas externos
    
    **Parâmetros:**
    - `id` (str, obrigatório): ID do pedido
    
    **Exemplo:**
    ```python
    pedido = consultar_pedido(id='123')
    ```
    
    **Tools Relacionadas:** `incluir_pedido`, `pedido_status`
    """
    params = {}

    result = client.get("/INTEGRACAO/PEDIDO_COMBUSTIVEL/PEDIDO/{id}", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def excluir_pedido(id: str) -> str:
    """
    **Exclui pedido de combustível.**
    
    Remove pedido não faturado do sistema. Pedidos já faturados
    não podem ser excluídos.
    
    **Quando usar:**
    - Cancelar pedidos não faturados
    - Correção de erros de cadastro
    - Gestão de pedidos pendentes
    
    **Parâmetros:**
    - `id` (str, obrigatório): ID do pedido a excluir
    
    **Exemplo:**
    ```python
    excluir_pedido(id='123')
    ```
    
    **Tools Relacionadas:** `consultar_pedido`, `pedido_status`
    """
    endpoint = f"/INTEGRACAO/PEDIDO_COMBUSTIVEL/PEDIDO/{id}"
    params = {}

    result = client.delete(endpoint, params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return "Registro excluído com sucesso."


@mcp.tool()
def pedido_xml(id: str) -> str:
    """
    **Retorna XML da NFe do pedido.**
    
    Obtém arquivo XML completo da NFe gerada no faturamento do pedido
    para integrações e validações fiscais.
    
    **Quando usar:**
    - Integrações contábeis
    - Validação fiscal
    - Envio de NFe ao cliente
    
    **Parâmetros:**
    - `id` (str, obrigatório): ID do pedido faturado
    
    **Exemplo:**
    ```python
    xml = pedido_xml(id='123')
    ```
    
    **Tools Relacionadas:** `pedido_danfe`, `pedido_faturar`
    """
    params = {}

    result = client.get("/INTEGRACAO/PEDIDO_COMBUSTIVEL/PEDIDO/{id}/XML", params=params)
    if not result["success"]:
        return f"Erro: {result.get('error', 'Erro desconhecido')}"
    return format_response(result.get("data", {}))


@mcp.tool()
def pedido_status(pedidos: Optional[list] = None) -> str:
    """
    **Consulta status de múltiplos pedidos.**
    
    Retorna status atual de uma lista de pedidos (pendente, faturado,
    cancelado, etc.) para acompanhamento em lote.
    
    **Quando usar:**
    - Monitorar múltiplos pedidos
    - Dashboards de gestão
    - Integrações com sistemas externos
    
    **Parâmetros:**
    - `pedidos` (list, opcional): Lista de IDs de pedidos
    
    **Exemplo:**
    ```python
    status = pedido_status(pedidos=['123', '124', '125'])
    ```
    
    **Tools Relacionadas:** `consultar_pedido`, `pedido_faturar`
    """
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
    """
    **Executa relatório personalizado configurado no sistema.**

    Esta tool permite executar relatórios personalizados previamente configurados
    no webPosto, aplicando filtros dinâmicos. É ideal para relatórios complexos
    e customizados por cliente.

    **Quando usar:**
    - Para executar relatórios customizados do sistema
    - Para gerar relatórios específicos do negócio
    - Para integrações com BI e dashboards
    - Para relatórios gerenciais personalizados

    **Conceito:**
    No webPosto, usuários podem criar relatórios personalizados via interface,
    definindo campos, filtros, agrupamentos e fórmulas. Esta tool executa esses
    relatórios via API, permitindo automação e integração.

    **Fluxo de Uso Essencial:**
    1. **Identifique o Relatório:** Obtenha o código do relatório no webPosto.
    2. **Prepare os Filtros:** Monte parâmetros conforme o relatório.
    3. **Execute:** Chame `relatorio_personalizado` com código e filtros.

    **Parâmetros:**
    - `relatorio_codigo` (str, obrigatório): Código do relatório personalizado.
      Obter via: Interface do webPosto ou documentação do cliente
      Exemplo: "REL-VENDAS-001"
    - **Filtros Dinâmicos (opcionais):** Varia conforme o relatório.
      Filtros comuns:
      * `data_inicial` (str): Data inicial (YYYY-MM-DD)
      * `data_final` (str): Data final (YYYY-MM-DD)
      * `filial` (List[int]): Lista de filiais
      * `cliente` (List[int]): Lista de clientes
      * `funcionario` (List[int]): Lista de funcionários
      * `produto` (List[int]): Lista de produtos
      * `grupo_produto` (List[int]): Lista de grupos
      * `fornecedor` (List[int]): Lista de fornecedores
      * `conta` (List[int]): Lista de contas bancárias
      * `centro_custo` (List[int]): Lista de centros de custo
      * `placa` (str): Placa de veículo
      * `nota` (str): Número de nota fiscal

    **Retorno:**
    Estrutura varia conforme o relatório configurado. Geralmente contém:
    - Colunas definidas no relatório
    - Dados filtrados e agrupados
    - Totalizadores (se configurados)
    - Gráficos (se configurados)

    **Exemplo de Uso (Python):**
    ```python
    # Cenário 1: Executar relatório de vendas por cliente
    relatorio = relatorio_personalizado(
        relatorio_codigo="REL-VENDAS-CLIENTE",
        data_inicial="2025-01-01",
        data_final="2025-01-31",
        filial=[7]
    )

    # Cenário 2: Relatório de estoque por grupo
    relatorio = relatorio_personalizado(
        relatorio_codigo="REL-ESTOQUE-GRUPO",
        data_posicao="2025-01-10",
        filial=[7],
        grupo_produto=[1, 2, 3]
    )

    # Cenário 3: Relatório financeiro personalizado
    relatorio = relatorio_personalizado(
        relatorio_codigo="REL-FIN-CONTAS-PAGAR",
        data_inicial="2025-01-01",
        data_final="2025-01-31",
        fornecedor=[456, 789],
        situacao_receber="PENDENTE"
    )

    # Cenário 4: Relatório de frota
    relatorio = relatorio_personalizado(
        relatorio_codigo="REL-FROTA-CONSUMO",
        data_inicial="2025-01-01",
        data_final="2025-01-31",
        cliente=[123],  # Cliente de frota
        placa="ABC1234"
    )
    ```

    **Dependências:**
    - Requer: Relatório personalizado configurado no webPosto

    **Tools Relacionadas:**
    - `consultar_venda` - Consultar vendas (genérico)
    - `vendas_periodo` - Relatório de vendas por período
    - `produtividade_funcionario` - Relatório de produtividade

    **Limitações:**
    - Relatório deve estar previamente configurado no webPosto
    - Filtros disponíveis dependem da configuração do relatório
    - Estrutura de retorno varia conforme configuração

    **Dica:**
    Para descobrir quais filtros um relatório aceita, consulte a documentação
    do relatório no webPosto ou teste com filtros comuns (data, filial, etc.).

    **Nota Importante:**
    Esta tool é altamente flexível mas requer conhecimento prévio dos
    relatórios configurados no sistema. Trabalhe com o cliente para identificar
    os códigos e filtros dos relatórios disponíveis.
    """
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
    """
    **Gera relatório de produtividade de funcionários.**

    Esta tool retorna métricas de desempenho e produtividade de funcionários,
    incluindo vendas, ticket médio, comissões e metas. É essencial para
    gestão de equipe e avaliação de desempenho.

    **Quando usar:**
    - Para avaliar desempenho de funcionários
    - Para calcular comissões
    - Para acompanhamento de metas
    - Para relatórios gerenciais de RH
    - Para análise de produtividade

    **Tipos de Relatório:**
    - **SINTETICO**: Resumo por funcionário (totais)
    - **ANALITICO**: Detalhado com vendas individuais
    - **COMISSAO**: Foco em comissões e bonificações

    **Fluxo de Uso Essencial:**
    1. **Defina o Tipo:** Escolha tipo de relatório (sintético/analítico).
    2. **Configure Filtros:** Defina período, funcionários, filiais.
    3. **Execute:** Chame `produtividade_funcionario`.

    **Parâmetros Principais:**
    - `tipo_relatorio` (str, obrigatório): Tipo do relatório.
      Valores: "SINTETICO", "ANALITICO", "COMISSAO"
    - `data_inicial` (str, opcional): Data inicial (YYYY-MM-DD).
      Exemplo: "2025-01-01"
    - `data_final` (str, opcional): Data final (YYYY-MM-DD).
      Exemplo: "2025-01-31"
    - `tipo_data` (str, opcional): Tipo de data para filtro.
      Valores: "VENDA", "PAGAMENTO"
      Default: "VENDA"
    - `funcionario` (int, opcional): Funcionário específico.
      Obter via: `consultar_funcionario`
    - `filial` (List[int], opcional): Lista de filiais.
      Obter via: `consultar_empresa`
    - `produto` (int, opcional): Produto específico.
    - `grupo_produto` (List[int], opcional): Grupos de produtos.
    - `caixa` (List[int], opcional): Lista de caixas/PDVs.
    - `ordenacao` (str, opcional): Campo de ordenação.
      Valores: "NOME", "VALOR", "QUANTIDADE"
    - `comissao` (str, opcional): Filtro de comissão.
      Valores: "COM_COMISSAO", "SEM_COMISSAO", "TODOS"
    - `calculo_ticket_medio` (str, opcional): Método de cálculo.
      Valores: "VALOR_TOTAL", "QUANTIDADE_VENDAS"

    **Retorno:**
    Estrutura varia conforme tipo de relatório:
    - **Sintético:**
      * Funcionário (código e nome)
      * Total de vendas (valor)
      * Quantidade de vendas
      * Ticket médio
      * Comissão total
      * Meta (se configurada)
      * % da meta atingida
    - **Analítico:**
      * Todas as informações do sintético
      * Detalhamento por venda
      * Produtos vendidos
      * Formas de pagamento

    **Exemplo de Uso (Python):**
    ```python
    # Cenário 1: Produtividade mensal de todos os funcionários
    relatorio = produtividade_funcionario(
        tipo_relatorio="SINTETICO",
        data_inicial="2025-01-01",
        data_final="2025-01-31",
        filial=[7],
        ordenacao="VALOR"
    )

    # Cenário 2: Detalhamento de funcionário específico
    relatorio = produtividade_funcionario(
        tipo_relatorio="ANALITICO",
        data_inicial="2025-01-01",
        data_final="2025-01-31",
        funcionario=10,
        filial=[7]
    )

    # Cenário 3: Relatório de comissões
    relatorio = produtividade_funcionario(
        tipo_relatorio="COMISSAO",
        data_inicial="2025-01-01",
        data_final="2025-01-31",
        filial=[7],
        comissao="COM_COMISSAO"
    )

    # Cenário 4: Ranking de vendedores
    relatorio = produtividade_funcionario(
        tipo_relatorio="SINTETICO",
        data_inicial="2025-01-01",
        data_final="2025-01-31",
        filial=[7],
        ordenacao="VALOR"
    )
    
    # Ordenar por valor decrescente
    ranking = sorted(
        relatorio,
        key=lambda x: x["valorTotal"],
        reverse=True
    )
    
    print("Ranking de Vendedores:")
    for i, func in enumerate(ranking[:10], 1):
        print(f"{i}. {func['nome']}: R$ {func['valorTotal']:,.2f}")

    # Cenário 5: Análise de ticket médio
    relatorio = produtividade_funcionario(
        tipo_relatorio="SINTETICO",
        data_inicial="2025-01-01",
        data_final="2025-01-31",
        filial=[7],
        calculo_ticket_medio="VALOR_TOTAL"
    )
    
    for func in relatorio:
        ticket = func["valorTotal"] / func["quantidadeVendas"] if func["quantidadeVendas"] > 0 else 0
        print(f"{func['nome']}: Ticket Médio R$ {ticket:.2f}")
    ```

    **Dependências:**
    - Opcional: `consultar_funcionario` (para obter funcionario)
    - Opcional: `consultar_empresa` (para obter filial)
    - Opcional: `consultar_produto` (para obter produto)

    **Tools Relacionadas:**
    - `consultar_funcionario` - Consultar funcionários
    - `consultar_venda` - Consultar vendas
    - `vendas_periodo` - Relatório de vendas

    **Métricas Calculadas:**
    - **Ticket Médio**: Valor total / Quantidade de vendas
    - **Comissão**: Baseada em regras configuradas
    - **% Meta**: (Valor vendido / Meta) * 100

    **Dica de Gestão:**
    Use este relatório mensalmente para:
    - Avaliar desempenho individual e da equipe
    - Identificar top performers
    - Calcular comissões e bonificações
    - Ajustar metas e estratégias de vendas
    """
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
