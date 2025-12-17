#!/usr/bin/env python3

import logging
import requests
from typing import Any, Dict, Optional

from src.config import settings

logger = logging.getLogger(__name__)

class WebPostoApiClient:
    """Cliente para interagir com a API do WebPosto."""

    def __init__(self):
        self.base_url = settings.WEBPOSTO_API_URL
        self.api_key = settings.WEBPOSTO_API_KEY
        self.headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'X-API-Key': self.api_key
        }

    def _request(self, method: str, endpoint: str, params: Optional[Dict[str, Any]] = None, json_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Método genérico para realizar requisições à API."""
        url = f"{self.base_url}{endpoint}"
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                params=params,
                json=json_data,
                timeout=30  # 30 segundos de timeout
            )
            response.raise_for_status()  # Lança exceção para status de erro (4xx ou 5xx)

            if response.status_code == 204:  # No Content
                return {"success": True, "data": None}
            
            return {"success": True, "data": response.json()}

        except requests.exceptions.HTTPError as http_err:
            logger.error(f"Erro HTTP ao acessar {url}: {http_err} - {response.text}")
            return {"success": False, "error": f"Erro na API: {response.status_code} - {response.text}"}
        except requests.exceptions.RequestException as req_err:
            logger.error(f"Erro de requisição ao acessar {url}: {req_err}")
            return {"success": False, "error": f"Erro de comunicação com a API: {req_err}"}

    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self._request("GET", endpoint, params=params)

    def post(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return self._request("POST", endpoint, json_data=data)

    def put(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return self._request("PUT", endpoint, json_data=data)

    def delete(self, endpoint: str) -> Dict[str, Any]:
        return self._request("DELETE", endpoint)

# Instância única do cliente para ser usada em toda a aplicação
api_client = WebPostoApiClient()
