#!/usr/bin/env python3
"""
WebPosto MCP Server - AWS Lambda Handler
Quality Automação

Este módulo fornece o handler para execução do servidor MCP como AWS Lambda.
Utiliza Mangum para adaptar requisições HTTP para o formato ASGI.
"""

import json
import logging
import os
from typing import Any, Dict

# AWS Lambda Powertools para logging e tracing
try:
    from aws_lambda_powertools import Logger, Tracer, Metrics
    from aws_lambda_powertools.utilities.typing import LambdaContext
    from aws_lambda_powertools.metrics import MetricUnit
    
    logger = Logger()
    tracer = Tracer()
    metrics = Metrics()
except ImportError:
    # Fallback para logging padrão se Powertools não estiver disponível
    import logging
    logger = logging.getLogger(__name__)
    tracer = None
    metrics = None

from mangum import Mangum

# Importar o servidor MCP
from src.server import mcp, client

# =============================================================================
# CONFIGURAÇÃO
# =============================================================================

# Configurar logging
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
logging.basicConfig(level=getattr(logging, LOG_LEVEL))

# =============================================================================
# HANDLER PRINCIPAL
# =============================================================================

def process_mcp_request(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Processa uma requisição MCP.
    
    Args:
        event: Evento da requisição contendo o corpo da mensagem MCP.
        
    Returns:
        Resposta formatada para o cliente MCP.
    """
    try:
        body = event.get('body', '{}')
        if isinstance(body, str):
            body = json.loads(body)
        
        # Extrair informações da requisição MCP
        method = body.get('method', '')
        params = body.get('params', {})
        request_id = body.get('id', None)
        
        logger.info(f"Processando requisição MCP: {method}")
        
        # Processar diferentes métodos MCP
        if method == 'tools/list':
            # Listar ferramentas disponíveis
            tools_list = []
            for tool_name, tool_func in mcp._tools.items():
                tools_list.append({
                    'name': tool_name,
                    'description': tool_func.__doc__ or '',
                    'inputSchema': getattr(tool_func, '_input_schema', {})
                })
            
            return {
                'jsonrpc': '2.0',
                'id': request_id,
                'result': {'tools': tools_list}
            }
        
        elif method == 'tools/call':
            # Executar uma ferramenta
            tool_name = params.get('name', '')
            tool_args = params.get('arguments', {})
            
            if tool_name not in mcp._tools:
                return {
                    'jsonrpc': '2.0',
                    'id': request_id,
                    'error': {
                        'code': -32601,
                        'message': f'Ferramenta não encontrada: {tool_name}'
                    }
                }
            
            # Executar a ferramenta
            tool_func = mcp._tools[tool_name]
            result = tool_func(**tool_args)
            
            if metrics:
                metrics.add_metric(name='ToolCalls', unit=MetricUnit.Count, value=1)
            
            return {
                'jsonrpc': '2.0',
                'id': request_id,
                'result': {
                    'content': [{'type': 'text', 'text': str(result)}]
                }
            }
        
        elif method == 'initialize':
            # Inicialização do cliente MCP
            return {
                'jsonrpc': '2.0',
                'id': request_id,
                'result': {
                    'protocolVersion': '2024-11-05',
                    'serverInfo': {
                        'name': 'webposto-mcp',
                        'version': '1.0.0'
                    },
                    'capabilities': {
                        'tools': {}
                    }
                }
            }
        
        else:
            return {
                'jsonrpc': '2.0',
                'id': request_id,
                'error': {
                    'code': -32601,
                    'message': f'Método não suportado: {method}'
                }
            }
            
    except json.JSONDecodeError as e:
        logger.error(f"Erro ao decodificar JSON: {e}")
        return {
            'jsonrpc': '2.0',
            'id': None,
            'error': {
                'code': -32700,
                'message': 'Parse error'
            }
        }
    except Exception as e:
        logger.error(f"Erro ao processar requisição: {e}")
        return {
            'jsonrpc': '2.0',
            'id': request_id if 'request_id' in locals() else None,
            'error': {
                'code': -32603,
                'message': str(e)
            }
        }


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handler principal da função Lambda.
    
    Args:
        event: Evento da API Gateway ou invocação direta.
        context: Contexto de execução da Lambda.
        
    Returns:
        Resposta HTTP formatada para API Gateway.
    """
    logger.info(f"Evento recebido: {json.dumps(event)[:500]}")
    
    # Verificar se é uma requisição HTTP (API Gateway)
    if 'httpMethod' in event or 'requestContext' in event:
        # Processar como requisição HTTP
        response = process_mcp_request(event)
        
        return {
            'statusCode': 200 if 'result' in response else 400,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type, X-API-Key',
                'Access-Control-Allow-Methods': 'POST, OPTIONS'
            },
            'body': json.dumps(response)
        }
    
    # Invocação direta (não HTTP)
    return process_mcp_request(event)


# Handler para Mangum (ASGI adapter)
# Útil se você quiser usar FastAPI ou similar
# mangum_handler = Mangum(app, lifespan="off")
