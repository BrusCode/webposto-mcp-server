"""
WebPosto MCP Server - Resources e Prompts
Implementação de Resources (documentação) e Prompts (templates) para o servidor MCP.

Autor: Quality Automação
Versão: 1.0.0
"""

import os
import json
from pathlib import Path
from typing import Any, Dict, List

# =============================================================================
# RESOURCES - Documentação e Schemas
# =============================================================================

def get_resources_list() -> List[Dict[str, Any]]:
    """Retorna lista de resources disponíveis."""
    return [
        {
            "uri": "file:///docs/GUIA_USO_APIS.md",
            "name": "Guia de Uso das APIs",
            "description": "Documentação completa sobre como usar as APIs do webPosto",
            "mimeType": "text/markdown"
        },
        {
            "uri": "file:///docs/mapeamento_dependencias_apis.md",
            "name": "Mapeamento de Dependências",
            "description": "Mapeamento completo das dependências entre APIs e fluxos de dados",
            "mimeType": "text/markdown"
        },
        {
            "uri": "file:///docs/prompt_agente_webposto.md",
            "name": "Prompt do Agente webPosto",
            "description": "Prompt otimizado para agentes de IA interagirem com o sistema webPosto",
            "mimeType": "text/markdown"
        },
        {
            "uri": "schema://tools",
            "name": "Schema das Tools MCP",
            "description": "Schema JSON com todas as tools disponíveis no servidor MCP",
            "mimeType": "application/json"
        }
    ]

def read_resource(uri: str) -> str:
    """Lê o conteúdo de um resource."""
    if uri.startswith("file:///docs/"):
        # Extrair o nome do arquivo
        filename = uri.replace("file:///docs/", "")
        docs_path = Path(__file__).parent.parent / "docs" / filename
        
        if docs_path.exists():
            with open(docs_path, 'r', encoding='utf-8') as f:
                return f.read()
        else:
            return f"Erro: Arquivo não encontrado: {filename}"
    
    elif uri == "schema://tools":
        # Retornar schema das tools (será gerado dinamicamente)
        return json.dumps({
            "description": "Schema das tools MCP do webPosto",
            "note": "Este schema é gerado dinamicamente pelo servidor MCP",
            "tools_count": "144 tools disponíveis",
            "categories": [
                "Vendas e Abastecimento",
                "Financeiro",
                "Estoque e Produtos",
                "Fiscal e Documentos",
                "Cadastros",
                "Relatórios e Análises",
                "Compras e Fornecedores",
                "Pedidos",
                "Configurações"
            ]
        }, indent=2)
    
    return "Erro: Resource não encontrado"

# =============================================================================
# PROMPTS - Templates Pré-configurados
# =============================================================================

def get_prompts_list() -> List[Dict[str, Any]]:
    """Retorna lista de prompts disponíveis."""
    return [
        {
            "name": "analise_vendas",
            "description": "Análise completa de vendas e faturamento",
            "arguments": [
                {
                    "name": "periodo",
                    "description": "Período para análise (ex: 'últimos 30 dias', 'mês atual')",
                    "required": True
                },
                {
                    "name": "unidade_negocio",
                    "description": "Código da unidade de negócio",
                    "required": False
                }
            ]
        },
        {
            "name": "consulta_estoque",
            "description": "Consulta detalhada de estoque e produtos",
            "arguments": [
                {
                    "name": "tipo_produto",
                    "description": "Tipo de produto (combustível, conveniência, todos)",
                    "required": False
                },
                {
                    "name": "unidade_negocio",
                    "description": "Código da unidade de negócio",
                    "required": False
                }
            ]
        },
        {
            "name": "relatorio_financeiro",
            "description": "Relatório financeiro completo (contas a pagar e receber)",
            "arguments": [
                {
                    "name": "periodo",
                    "description": "Período para análise (ex: 'mês atual', 'próximos 7 dias')",
                    "required": True
                },
                {
                    "name": "tipo",
                    "description": "Tipo de relatório (pagar, receber, ambos)",
                    "required": False
                }
            ]
        },
        {
            "name": "analise_abastecimento",
            "description": "Análise detalhada de abastecimentos e equipamentos",
            "arguments": [
                {
                    "name": "periodo",
                    "description": "Período para análise",
                    "required": True
                },
                {
                    "name": "bomba_codigo",
                    "description": "Código da bomba (opcional, para análise específica)",
                    "required": False
                }
            ]
        }
    ]

def get_prompt(name: str, arguments: Dict[str, Any]) -> str:
    """Retorna o prompt formatado com os argumentos."""
    
    if name == "analise_vendas":
        periodo = arguments.get("periodo", "últimos 30 dias")
        unidade = arguments.get("unidade_negocio", "todas")
        
        return f"""Realize uma análise completa de vendas para o período: {periodo}.

**Etapas da Análise:**

1. **Consultar Vendas do Período**
   - Use `vendas_periodo` para obter vendas do período especificado
   - Filtre por unidade de negócio: {unidade}

2. **Análise de Produtos**
   - Identifique os produtos mais vendidos
   - Separe vendas de combustíveis vs. conveniência
   - Calcule ticket médio por tipo de produto

3. **Análise de Abastecimentos** (se aplicável)
   - Use `consultar_abastecimento` para detalhes de combustíveis
   - Analise volume por bomba/bico
   - Identifique padrões de horário de pico

4. **Métricas Financeiras**
   - Faturamento total do período
   - Comparação com período anterior (se possível)
   - Margem de lucro por categoria

5. **Insights e Recomendações**
   - Identifique tendências
   - Sugira ações para otimização
   - Destaque produtos com baixa performance

**Formato de Saída:**
Apresente os resultados de forma clara e estruturada, com gráficos textuais quando apropriado."""

    elif name == "consulta_estoque":
        tipo = arguments.get("tipo_produto", "todos")
        unidade = arguments.get("unidade_negocio", "todas")
        
        return f"""Realize uma consulta detalhada de estoque.

**Parâmetros:**
- Tipo de produto: {tipo}
- Unidade de negócio: {unidade}

**Etapas:**

1. **Consultar Produtos**
   - Use `consultar_produto` para listar produtos ativos
   - Filtre por tipo: {tipo}

2. **Verificar Estoque**
   - Use `estoque` para obter quantidades atuais
   - Identifique produtos com estoque baixo
   - Verifique produtos com estoque zerado

3. **Análise de Movimentação**
   - Identifique produtos com alta rotatividade
   - Produtos com baixa movimentação (estoque parado)

4. **Recomendações**
   - Produtos que precisam de reposição urgente
   - Produtos para promoção (estoque alto)
   - Sugestões de ajuste de estoque mínimo

**Formato de Saída:**
Tabela com: Produto | Estoque Atual | Status | Recomendação"""

    elif name == "relatorio_financeiro":
        periodo = arguments.get("periodo", "mês atual")
        tipo = arguments.get("tipo", "ambos")
        
        return f"""Gere um relatório financeiro completo para: {periodo}.

**Tipo de Relatório:** {tipo}

**Etapas:**

1. **Títulos a Pagar** (se tipo = 'pagar' ou 'ambos')
   - Use `consultar_titulo_pagar` com filtros de data
   - Agrupe por status (aberto, vencido, pago)
   - Calcule total de obrigações

2. **Títulos a Receber** (se tipo = 'receber' ou 'ambos')
   - Use `consultar_titulo_receber` com filtros de data
   - Agrupe por status (aberto, vencido, recebido)
   - Calcule total de recebíveis

3. **Análise de Fluxo de Caixa**
   - Compare entradas vs. saídas
   - Identifique títulos vencidos
   - Calcule saldo projetado

4. **Alertas e Ações**
   - Títulos vencidos que precisam de atenção
   - Títulos próximos do vencimento
   - Recomendações de cobrança/pagamento

**Formato de Saída:**
Resumo executivo + tabelas detalhadas por categoria"""

    elif name == "analise_abastecimento":
        periodo = arguments.get("periodo", "últimos 7 dias")
        bomba = arguments.get("bomba_codigo", "todas")
        
        return f"""Análise detalhada de abastecimentos.

**Parâmetros:**
- Período: {periodo}
- Bomba: {bomba}

**Etapas:**

1. **Consultar Abastecimentos**
   - Use `consultar_abastecimento` para o período
   - Filtre por bomba se especificado: {bomba}

2. **Análise por Equipamento**
   - Use `consultar_bomba` e `consultar_bico` para detalhes
   - Volume total por bomba/bico
   - Identifique equipamentos mais utilizados

3. **Análise de Produtos**
   - Volume por tipo de combustível
   - Preço médio praticado
   - Comparação entre produtos

4. **Performance Operacional**
   - Horários de pico de abastecimento
   - Tempo médio de abastecimento
   - Eficiência por equipamento

5. **Insights**
   - Equipamentos com baixa utilização
   - Oportunidades de otimização
   - Recomendações de manutenção

**Formato de Saída:**
Dashboard textual com métricas-chave e gráficos"""

    return f"Erro: Prompt '{name}' não encontrado"
