# Guia de Uso das APIs WebPosto

## Visão Geral

Este guia fornece informações essenciais para o uso correto das APIs do sistema WebPosto através do servidor MCP.

## Princípios Fundamentais

### 1. Padrão Multi-Tenant

O sistema WebPosto opera em um modelo **multi-tenant**, onde múltiplas unidades de negócio (filiais/empresas) compartilham a mesma instalação, mas mantêm dados transacionais isolados.

**Implicação Prática:**
- Quase todos os endpoints requerem o parâmetro `empresaCodigo` (ou `filial`)
- O endpoint `/INTEGRACAO/EMPRESAS` é o ponto de partida obrigatório
- Sempre consulte empresas antes de realizar outras operações

### 2. Hierarquia de Entidades

```
Empresa (Filial) [Nível 1 - Base]
├── Produtos [Nível 2 - Cadastros]
│   ├── Grupos de Produto
│   ├── Sub-Grupos de Produto
│   └── Estoque por Empresa
├── Clientes [Nível 2 - Cadastros]
│   ├── Grupos de Cliente
│   └── Clientes por Empresa
├── Funcionários [Nível 2 - Cadastros]
├── Equipamentos [Nível 2 - Cadastros]
│   ├── Bombas
│   ├── Bicos
│   ├── Tanques
│   └── PDV/Caixa
└── Transações [Nível 3 - Operações]
    ├── Vendas
    ├── Abastecimentos
    └── Movimentos Financeiros
```

## Fluxos de Trabalho Comuns

### Fluxo 1: Consultar Vendas de uma Empresa

```python
# 1. Obter lista de empresas
empresas = consultar_empresas()
# Resultado: [{"codigo": 7, "razaoSocial": "Posto Centro"}, ...]

# 2. Consultar vendas da empresa
vendas = consultar_venda(
    data_inicial="2025-01-01",
    data_final="2025-01-10",
    empresa_codigo=7
)
```

### Fluxo 2: Consultar Vendas de um Produto Específico

```python
# 1. Obter empresa
empresas = consultar_empresas()
empresa_codigo = 7

# 2. Listar produtos da empresa
produtos = consultar_produto(empresa_codigo=7)
# Resultado: [{"codigo": 150, "descricao": "Gasolina Comum"}, ...]

# 3. Consultar vendas do produto
relatorio = vendas_periodo(
    data_inicial="2025-01-01",
    data_final="2025-01-31",
    filial=[7],
    produto=[150],
    tipo_data="FISCAL",
    ordenacao_por="QUANTIDADE_VENDIDA",
    cupom_cancelado=False
)
```

### Fluxo 3: Consultar Estoque de Produto

```python
# 1. Obter empresa e produto
empresa_codigo = 7
produto_codigo = 150

# 2. Consultar estoque
estoque = consultar_estoque_periodo(
    data_final="2025-01-10",
    empresa_codigo=empresa_codigo,
    produto_codigo=produto_codigo
)
```

### Fluxo 4: Receber Pagamento

```python
# 1. Consultar venda
vendas = consultar_venda(
    data_inicial="2025-01-10",
    data_final="2025-01-10",
    empresa_codigo=7
)
venda_codigo = vendas[0]["codigo"]

# 2. Receber título
resultado = receber_titulo(
    dados={
        "tituloCodigo": 12345,
        "dataRecebimento": "2025-01-10",
        "valorRecebido": 1500.50,
        "formaPagamento": "P"  # PIX
    }
)
```

## Formatos de Dados

### Datas
- **Formato**: `YYYY-MM-DD`
- **Exemplo**: `"2025-01-10"`

### Listas
- **Formato**: Array Python `[valor1, valor2]`
- **Exemplo**: `filial=[7, 8, 9]`

### Booleanos
- **Formato**: `True` ou `False` (Python)
- **Exemplo**: `cupom_cancelado=False`

## Valores Válidos para Enums

### Campo: situacao (Situação da Venda)
- `"A"` - Ativo/Aberto
- `"C"` - Cancelado
- `"F"` - Finalizado
- `"P"` - Pendente

### Campo: tipoData (Tipo de Data)
- `"FISCAL"` - Data fiscal da venda
- `"MOVIMENTO"` - Data de movimento

### Campo: ordenacaoPor (Ordenação)
- `"REFERENCIA"` - Por referência
- `"PRODUTO"` - Por produto
- `"PARTICIPACAO"` - Por participação
- `"QUANTIDADE_VENDIDA"` - Por quantidade vendida

### Campo: agrupamentoPor (Agrupamento)
- `"SEM_AGRUPAMENTO"` - Sem agrupamento
- `"PRODUTO"` - Por produto
- `"CLIENTE"` - Por cliente
- `"DIA"` - Por dia
- `"MES"` - Por mês
- `"ANO"` - Por ano

### Campo: tipoProduto (Tipo de Produto)
- `"COMBUSTIVEL"` - Combustíveis
- `"PRODUTO"` - Produtos da loja
- `"SERVICO"` - Serviços

### Campo: deptoSelcon (Departamento)
- `"PISTA"` - Combustíveis (pista)
- `"LOJA"` - Loja de conveniência
- `"AMBOS"` - Ambos os departamentos

### Campo: formaPagamento (Forma de Pagamento)
- `"D"` - Dinheiro
- `"C"` - Cheque
- `"T"` - Transferência
- `"P"` - PIX
- `"CC"` - Cartão de Crédito
- `"CD"` - Cartão de Débito

## Limites e Paginação

### Limites Padrão
- **Limite padrão**: 100 registros
- **Limite máximo**: 2000 registros

### Paginação
Use o parâmetro `ultimoCodigo` para paginar resultados:

```python
# Primeira página
resultado1 = consultar_produto(empresa_codigo=7, limite=100)

# Segunda página
ultimo_codigo = resultado1[-1]["codigo"]
resultado2 = consultar_produto(
    empresa_codigo=7, 
    limite=100,
    ultimo_codigo=ultimo_codigo
)
```

## Erros Comuns e Como Evitar

### Erro 1: ID não encontrado
**Causa**: Usar ID sem consultar antes  
**Solução**: Sempre consulte o endpoint correspondente para obter IDs válidos

### Erro 2: Parâmetro obrigatório faltando
**Causa**: Não informar campo obrigatório  
**Solução**: Consulte a documentação da tool para ver campos obrigatórios

### Erro 3: Formato de data inválido
**Causa**: Usar formato diferente de YYYY-MM-DD  
**Solução**: Sempre use o formato ISO 8601: `"2025-01-10"`

### Erro 4: Empresa não especificada
**Causa**: Não informar empresaCodigo em endpoint que requer  
**Solução**: Sempre consulte empresas primeiro e informe o código

## Boas Práticas

1. **Sempre consulte IDs antes de usar**
   - Nunca assuma valores de códigos
   - Sempre busque em endpoints de consulta

2. **Use filtros de data apropriados**
   - Considere o tipo de data (FISCAL vs MOVIMENTO)
   - Não use períodos muito longos sem paginação

3. **Respeite limites de paginação**
   - Use `limite` e `ultimoCodigo` para grandes volumes
   - Não tente buscar mais de 2000 registros de uma vez

4. **Trate erros adequadamente**
   - Verifique o campo "success" na resposta
   - Leia mensagens de erro em "error"

5. **Considere o contexto multi-tenant**
   - Sempre especifique empresaCodigo quando aplicável
   - Não misture dados de empresas diferentes

## Referências

- [Mapeamento de Dependências](./mapeamento_dependencias_apis.md)
- [Prompt para Agentes](./prompt_agente_webposto.md)
- [Documentação Swagger](https://web.qualityautomacao.com.br/webjars/swagger-ui/index.html)

---

**Versão**: 2.0  
**Data**: 10 de Janeiro de 2026  
**Autor**: Quality Automação
