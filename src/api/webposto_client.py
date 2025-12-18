#!/usr/bin/env python3
"""
WebPosto API Client - Quality Automação

Cliente HTTP para comunicação com a API do WebPosto.
A autenticação é feita via parâmetro "chave" na query string de cada requisição.

Exemplo de uso:
    client = WebPostoClient()
    result = client.get("/INTEGRACAO/VENDA", params={"dataInicial": "2025-12-18", "dataFinal": "2025-12-18"})
"""

import json
import logging
import os
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)

# Configuração
WEBPOSTO_BASE_URL = os.getenv('WEBPOSTO_URL', 'https://web.qualityautomacao.com.br')
API_KEY = os.getenv('WEBPOSTO_API_KEY', '')


class WebPostoClient:
    """
    Cliente HTTP para comunicação com a API WebPosto.
    
    A autenticação é feita via parâmetro "chave" na query string de cada requisição,
    conforme o padrão da API WebPosto.
    
    Atributos:
        base_url: URL base da API (padrão: https://web.qualityautomacao.com.br)
        timeout: Timeout das requisições em segundos (padrão: 30)
    """
    
    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None):
        """
        Inicializa o cliente.
        
        Args:
            base_url: URL base da API (opcional, usa variável de ambiente se não informado)
            api_key: Chave de autenticação (opcional, usa variável de ambiente se não informado)
        """
        self.base_url = (base_url or WEBPOSTO_BASE_URL).rstrip('/')
        self.api_key = api_key or API_KEY
        self.timeout = 30
    
    @property
    def headers(self) -> Dict[str, str]:
        """Retorna os headers padrão para requisições."""
        return {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
    
    def _add_auth_param(self, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Adiciona o parâmetro de autenticação 'chave' aos parâmetros da requisição.
        
        Args:
            params: Dicionário de parâmetros existentes
            
        Returns:
            Dicionário de parâmetros com a chave de autenticação adicionada
        """
        if params is None:
            params = {}
        
        if self.api_key:
            params['chave'] = self.api_key
        
        return params
    
    def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Executa uma requisição HTTP para a API.
        
        Args:
            method: Método HTTP (GET, POST, PUT, DELETE)
            endpoint: Endpoint da API (ex: /INTEGRACAO/VENDA)
            params: Parâmetros de query string
            data: Dados do corpo da requisição (para POST/PUT)
            
        Returns:
            Dicionário com o resultado da requisição:
            - success: bool indicando se a requisição foi bem-sucedida
            - data: dados da resposta (se sucesso)
            - error: mensagem de erro (se falha)
            - status_code: código HTTP da resposta
        """
        url = f"{self.base_url}{endpoint}"
        params = self._add_auth_param(params)
        
        try:
            logger.info(f"Requisição {method} para: {url}")
            logger.debug(f"Parâmetros: {params}")
            
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                params=params,
                json=data,
                timeout=self.timeout
            )
            
            logger.info(f"Status: {response.status_code}")
            
            # Resposta sem conteúdo (204 No Content)
            if response.status_code == 204:
                return {
                    "success": True,
                    "data": None,
                    "message": "Operação realizada com sucesso",
                    "status_code": 204
                }
            
            # Resposta de sucesso (2xx)
            if 200 <= response.status_code < 300:
                try:
                    return {
                        "success": True,
                        "data": response.json(),
                        "status_code": response.status_code
                    }
                except json.JSONDecodeError:
                    return {
                        "success": True,
                        "data": response.text,
                        "status_code": response.status_code
                    }
            
            # Erro de autenticação
            if response.status_code == 401:
                return {
                    "success": False,
                    "error": "Erro de autenticação. Verifique sua chave de API.",
                    "status_code": 401
                }
            
            # Erro de permissão
            if response.status_code == 403:
                return {
                    "success": False,
                    "error": "Acesso negado. Verifique as permissões da sua chave de API.",
                    "status_code": 403
                }
            
            # Recurso não encontrado
            if response.status_code == 404:
                return {
                    "success": False,
                    "error": "Recurso não encontrado.",
                    "status_code": 404
                }
            
            # Outros erros
            error_msg = response.text[:500] if response.text else f"Erro HTTP {response.status_code}"
            return {
                "success": False,
                "error": f"Erro {response.status_code}: {error_msg}",
                "status_code": response.status_code
            }
            
        except requests.exceptions.Timeout:
            logger.error(f"Timeout ao acessar {url}")
            return {
                "success": False,
                "error": f"Timeout na requisição ({self.timeout}s). Tente novamente."
            }
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Erro de conexão: {e}")
            return {
                "success": False,
                "error": f"Erro de conexão com o servidor. Verifique sua internet."
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro na requisição: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Executa uma requisição GET.
        
        Args:
            endpoint: Endpoint da API
            params: Parâmetros de query string
            
        Returns:
            Resultado da requisição
        """
        return self._make_request("GET", endpoint, params=params)
    
    def post(self, endpoint: str, data: Dict[str, Any], params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Executa uma requisição POST.
        
        Args:
            endpoint: Endpoint da API
            data: Dados do corpo da requisição
            params: Parâmetros de query string
            
        Returns:
            Resultado da requisição
        """
        return self._make_request("POST", endpoint, params=params, data=data)
    
    def put(self, endpoint: str, data: Dict[str, Any], params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Executa uma requisição PUT.
        
        Args:
            endpoint: Endpoint da API
            data: Dados do corpo da requisição
            params: Parâmetros de query string
            
        Returns:
            Resultado da requisição
        """
        return self._make_request("PUT", endpoint, params=params, data=data)
    
    def delete(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Executa uma requisição DELETE.
        
        Args:
            endpoint: Endpoint da API
            params: Parâmetros de query string
            
        Returns:
            Resultado da requisição
        """
        return self._make_request("DELETE", endpoint, params=params)
    
    def patch(self, endpoint: str, data: Dict[str, Any], params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Executa uma requisição PATCH.
        
        Args:
            endpoint: Endpoint da API
            data: Dados do corpo da requisição
            params: Parâmetros de query string
            
        Returns:
            Resultado da requisição
        """
        return self._make_request("PATCH", endpoint, params=params, data=data)


# Instância global do cliente para uso conveniente
default_client = WebPostoClient()
