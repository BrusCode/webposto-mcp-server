#!/usr/bin/env python3
"""
WebPosto MCP Server - AWS Lambda Handler (v2.0 - Produção)
Quality Automação

Este módulo fornece o handler para execução do servidor MCP como AWS Lambda.
Utiliza o AWS Lambda Powertools para boas práticas de logging, tracing e métricas.
"""

import json
import logging
import os
from typing import Any, Dict

import boto3
from botocore.exceptions import ClientError

# AWS Lambda Powertools
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext

# Importar o servidor MCP
from src.server import mcp, client

# =============================================================================
# CONFIGURAÇÃO
# =============================================================================

# Configurar Powertools
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logger = Logger(service="webposto-mcp", level=LOG_LEVEL)
tracer = Tracer(service="webposto-mcp")

# Cache para o secret da API
SECRET_CACHE: Dict[str, str] = {}

# =============================================================================
# FUNÇÕES AUXILIARES
# =============================================================================

@tracer.capture_method
def get_api_key_from_secrets_manager(secret_name: str) -> str:
    """
    Busca a chave da API do WebPosto no AWS Secrets Manager.
    Implementa um cache simples para evitar chamadas repetidas.
    """
    if secret_name in SECRET_CACHE:
        logger.info("Retornando chave da API do cache.")
        return SECRET_CACHE[secret_name]

    logger.info(f"Buscando secret [33m{secret_name}[0m no AWS Secrets Manager.")
    session = boto3.session.Session()
    sm_client = session.client(service_name="secretsmanager")

    try:
        get_secret_value_response = sm_client.get_secret_value(SecretId=secret_name)
    except ClientError as e:
        logger.exception("Não foi possível obter o secret do Secrets Manager.")
        raise e

    api_key = get_secret_value_response["SecretString"]
    SECRET_CACHE[secret_name] = api_key
    logger.info("Chave da API carregada e armazenada em cache.")
    return api_key

# =============================================================================
# HANDLER PRINCIPAL
# =============================================================================

@logger.inject_lambda_context(log_event=True)
@tracer.capture_lambda_handler
def handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Handler principal da função Lambda.
    Processa requisições da API Gateway e invoca o servidor MCP.
    """
    try:
        # 1. Obter chave da API do Secrets Manager
        secret_name = os.environ["WEBPOSTO_API_KEY_SECRET_NAME"]
        api_key = get_api_key_from_secrets_manager(secret_name)
        
        # 2. Configurar a chave no cliente HTTP
        client.set_api_key(api_key)

        # 3. Processar a requisição MCP
        body = event.get("body", "{}")
        if isinstance(body, str):
            body = json.loads(body)

        # Simular a comunicação stdio que o servidor MCP espera
        # O servidor MCP espera uma linha por vez
        response_str = mcp.process_request(json.dumps(body))
        response_data = json.loads(response_str)

        logger.info("Requisição MCP processada com sucesso.")

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
        logger.exception("Erro de parsing no corpo da requisição.")
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Corpo da requisição inválido (não é um JSON válido)"}),
        }
    except Exception as e:
        logger.exception("Ocorreu um erro inesperado.")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": f"Erro interno no servidor: {str(e)}"}),
        }
