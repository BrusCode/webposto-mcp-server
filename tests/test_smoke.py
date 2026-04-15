#!/usr/bin/env python3
"""
Smoke tests para o WebPosto MCP Server.

Verifica que os módulos principais importam corretamente e que a estrutura
básica do servidor está intacta, sem depender de credenciais ou rede.
"""

import importlib
import os
import sys

import pytest

# Garantir que o PYTHONPATH aponta para a raiz do projeto
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# Testes de importação — client canônico
# ---------------------------------------------------------------------------


def test_import_webposto_client():
    """WebPostoClient deve importar sem erros."""
    from src.api.webposto_client import WebPostoClient, default_client, api_client

    assert WebPostoClient is not None
    assert default_client is not None
    assert api_client is not None


def test_api_client_alias():
    """api_client deve ser o mesmo objeto que default_client."""
    from src.api.webposto_client import default_client, api_client

    assert api_client is default_client


def test_webposto_client_defaults():
    """WebPostoClient deve ter valores padrão corretos."""
    from src.api.webposto_client import WebPostoClient

    client = WebPostoClient()
    assert client.base_url == "https://web.qualityautomacao.com.br"
    assert client.timeout == 180


def test_webposto_client_normalize_params_booleans():
    """_normalize_params deve converter booleanos Python para string lowercase."""
    from src.api.webposto_client import WebPostoClient

    client = WebPostoClient()
    result = client._normalize_params({"ativo": True, "inativo": False, "nome": "teste"})
    assert result["ativo"] == "true"
    assert result["inativo"] == "false"
    assert result["nome"] == "teste"


def test_webposto_client_normalize_params_list():
    """_normalize_params deve normalizar booleanos dentro de listas."""
    from src.api.webposto_client import WebPostoClient

    client = WebPostoClient()
    result = client._normalize_params({"flags": [True, False, "outro"]})
    assert result["flags"] == ["true", "false", "outro"]


def test_webposto_client_normalize_params_none():
    """_normalize_params com None deve retornar dicionário vazio."""
    from src.api.webposto_client import WebPostoClient

    client = WebPostoClient()
    assert client._normalize_params(None) == {}


# ---------------------------------------------------------------------------
# Testes de importação — tools modulares
# ---------------------------------------------------------------------------


def test_import_abastecimento_tools():
    """Módulo de tools de abastecimento deve importar sem erros."""
    mod = importlib.import_module("src.tools.abastecimento_tools")
    assert hasattr(mod, "consultar_abastecimentos")


def test_import_caixa_tools():
    """Módulo de tools de caixa deve importar sem erros."""
    mod = importlib.import_module("src.tools.caixa_tools")
    assert hasattr(mod, "consultar_caixas")


def test_import_estoque_tools():
    """Módulo de tools de estoque deve importar sem erros."""
    mod = importlib.import_module("src.tools.estoque_tools")
    assert hasattr(mod, "consultar_estoque_produtos")


# ---------------------------------------------------------------------------
# Testes de configuração — variáveis de ambiente
# ---------------------------------------------------------------------------


def test_env_url_default(monkeypatch):
    """URL base padrão deve ser definida mesmo sem variável de ambiente."""
    monkeypatch.delenv("WEBPOSTO_URL", raising=False)

    # Reimportar o módulo para pegar o novo estado do ambiente
    import importlib
    import src.api.webposto_client as wc_mod

    importlib.reload(wc_mod)
    assert wc_mod.WEBPOSTO_BASE_URL == "https://web.qualityautomacao.com.br"


def test_env_url_override(monkeypatch):
    """WEBPOSTO_URL deve sobrescrever a URL padrão."""
    monkeypatch.setenv("WEBPOSTO_URL", "https://meu-servidor.com")

    import importlib
    import src.api.webposto_client as wc_mod

    importlib.reload(wc_mod)
    assert wc_mod.WEBPOSTO_BASE_URL == "https://meu-servidor.com"


# ---------------------------------------------------------------------------
# Testes do servidor MCP principal (apenas estrutura, sem rede)
# ---------------------------------------------------------------------------


def test_server_imports():
    """server.py deve importar sem erros (mesmo sem API key)."""
    import src.server as server_mod

    assert hasattr(server_mod, "mcp")
    assert hasattr(server_mod, "client")
    assert hasattr(server_mod, "WEBPOSTO_BASE_URL")
    assert hasattr(server_mod, "API_KEY")


def test_server_tool_count():
    """Servidor deve ter pelo menos 100 tools registradas."""
    import src.server as server_mod

    tools = server_mod.mcp._tools
    assert len(tools) >= 100, f"Esperado ≥100 tools, encontrado {len(tools)}"


def test_server_format_response_empty():
    """format_response deve retornar mensagem adequada para lista vazia."""
    from src.server import format_response

    result = format_response([])
    assert "Nenhum registro" in result


def test_server_format_response_list():
    """format_response deve formatar lista de registros corretamente."""
    from src.server import format_response

    data = [{"id": 1, "nome": "Teste"}]
    result = format_response(data)
    assert "Total de registros: 1" in result
    assert "Registro 1" in result


def test_server_format_response_cam_dad():
    """format_response deve tratar formato CAM/DAD da API WebPosto."""
    from src.server import format_response

    data = {"CAM": ["col1", "col2"], "DAD": [["val1", "val2"], ["val3", "val4"]]}
    result = format_response(data)
    assert "Total de registros: 2" in result
