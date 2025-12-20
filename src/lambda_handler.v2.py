#!/usr/bin/env python3
"""
WebPosto MCP Server - AWS Lambda Handler (v2.0 - Produção)
Quality Automação

Este módulo serve como o ponto de entrada (handler) para a execução do servidor
MCP em um ambiente AWS Lambda. Ele é projetado para ser invocado pela
API Gateway e gerencia o ciclo de vida da requisição, incluindo autenticação
segura e a comunicação com a lógica principal do servidor MCP.

Fluxo de Execução:
1.  A API Gateway recebe uma requisição POST e invoca esta função Lambda.
2.  O handler busca a chave da API do WebPosto no AWS Secrets Manager.
3.  A chave é injetada dinamicamente no módulo do servidor principal.
4.  O corpo da requisição (JSON-RPC) é passado para o servidor MCP.
5.  O servidor processa a requisição, chama a ferramenta apropriada e
    interage com a API do WebPosto.
6.  A resposta é retornada para a API Gateway e, por fim, para o cliente.
"""

import json
import os
from typing import Any, Dict

import boto3
from botocore.exceptions import ClientError

# AWS Lambda Powertools para boas práticas de observabilidade
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext

# Importa o módulo do servidor principal. É crucial que as ferramentas
# e o cliente HTTP já estejam definidos neste módulo.
from src import server as mcp_server

# =============================================================================
# CONFIGURAÇÃO
# =============================================================================

# Configurar Powertools para logging e tracing estruturado
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logger = Logger(service="webposto-mcp", level=LOG_LEVEL)
tracer = Tracer(service="webposto-mcp")

# Cache em memória para o secret da API, evitando chamadas repetidas ao
# Secrets Manager em invocações "quentes" da Lambda.
SECRET_CACHE: Dict[str, str] = {}

# =============================================================================
# FUNÇÕES AUXILIARES
# =============================================================================

@tracer.capture_method
def get_api_key_from_secrets_manager(secret_name: str) -> str:
    """
    Busca a chave da API do WebPosto no AWS Secrets Manager.

    Esta função se conecta ao serviço Secrets Manager da AWS para obter a
    credencial de forma segura. Para otimizar a performance e reduzir custos,
    ela implementa um cache em memória simples. A chave é buscada apenas na
    primeira invocação de uma instância "quente" da Lambda.

    Args:
        secret_name: O nome ou ARN do secret no Secrets Manager.

    Returns:
        A chave da API como uma string.

    Raises:
        ClientError: Se ocorrer um erro ao buscar o secret.
    """
    if secret_name in SECRET_CACHE:
        logger.info("Chave da API encontrada no cache. Retornando valor em memória.")
        return SECRET_CACHE[secret_name]

    logger.info(f"Buscando secret '{secret_name}' no AWS Secrets Manager.")
    session = boto3.session.Session()
    sm_client = session.client(service_name="secretsmanager")

    try:
        # Faz a chamada para a API do Secrets Manager
        get_secret_value_response = sm_client.get_secret_value(SecretId=secret_name)
        api_key = get_secret_value_response["SecretString"]

        # Armazena a chave no cache para futuras invocações
        SECRET_CACHE[secret_name] = api_key
        logger.info("Chave da API carregada do Secrets Manager e armazenada em cache.")
        return api_key

    except ClientError as e:
        logger.exception("Não foi possível obter o secret do Secrets Manager. Verifique as permissões da IAM Role e o nome do secret.")
        raise e

# =============================================================================
# HANDLER PRINCIPAL DA LAMBDA
# =============================================================================

@logger.inject_lambda_context(log_event=True)
@tracer.capture_lambda_handler
def handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Handler principal da função Lambda, invocado pela API Gateway.

    Este handler orquestra todo o processo:
    1.  Obtém a chave da API de forma segura.
    2.  Atualiza a configuração do cliente HTTP em tempo de execução.
    3.  Delega o processamento da requisição MCP para o servidor.
    4.  Formata e retorna a resposta HTTP.
    """
    try:
        # 1. Obter o nome do secret da variável de ambiente
        secret_name = os.environ["WEBPOSTO_API_KEY_SECRET_NAME"]
        api_key = get_api_key_from_secrets_manager(secret_name)

        # 2. Injetar a chave da API no módulo do servidor
        #    Isso atualiza a variável global que o `WebPostoClient` utiliza.
        mcp_server.API_KEY = api_key

        # 3. Processar a requisição MCP
        #    O corpo da requisição vem da API Gateway como uma string JSON.
        body_str = event.get("body", "{}")
        logger.info(f"Corpo da requisição recebido: {body_str}")

        # O servidor MCP espera uma linha de JSON por vez, simulando stdio.
        response_str = mcp_server.mcp.process_request(body_str)
        response_data = json.loads(response_str)

        logger.info(f"Resposta do servidor MCP: {response_data}")

        # 4. Retornar a resposta formatada para a API Gateway
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type,Authorization",
                "Access-Control-Allow-Methods": "POST,OPTIONS",
            },
            "body": json.dumps(response_data),
        }

    except json.JSONDecodeError as e:
        logger.exception("Erro de parsing no corpo da requisição. Não é um JSON válido.")
        return {
            "statusCode": 400,
            "body": json.dumps({"error": f"Corpo da requisição inválido: {e}"}),
        }
    except Exception as e:
        logger.exception("Ocorreu um erro inesperado durante a execução.")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": f"Erro interno no servidor: {str(e)}"}),
        }
