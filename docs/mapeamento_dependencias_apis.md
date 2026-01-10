# Mapeamento de Dependências e Fluxos de Uso - API WebPosto

## Visão Geral

Este documento mapeia as dependências entre os endpoints da API WebPosto, identificando quais endpoints devem ser consultados antes de outros para obter IDs e informações necessárias. Este mapeamento é essencial para que agentes de IA utilizem a API corretamente.

## Princípios Fundamentais

### 1. Padrão Multi-Tenant
**Conceito:** O WebPosto opera com múltiplas unidades de negócio (filiais) em uma única instalação.

**Implicação:** A maioria dos endpoints requer o parâmetro `empresaCodigo` ou `filial` para filtrar dados por unidade de negócio.

**Endpoint Base:** `/INTEGRACAO/EMPRESAS`
- **Uso:** Sempre consultar primeiro para obter lista de empresas/filiais disponíveis
- **Retorna:** Lista de empresas com seus códigos (IDs)
- **Quando usar:** No início de qualquer fluxo que necessite filtrar por empresa

### 2. Hierarquia de Entidades
O sistema possui uma hierarquia clara de entidades que deve ser respeitada:

```
Empresa (Filial)
├── Produtos
│   ├── Grupos de Produto
│   ├── Sub-Grupos de Produto
│   └── Estoque por Empresa
├── Clientes
│   ├── Grupos de Cliente
│   └── Clientes por Empresa
├── Funcionários
├── Equipamentos
│   ├── Bombas
│   ├── Bicos
│   ├── Tanques
│   └── PDV/Caixa
└── Transações
    ├── Vendas
    ├── Abastecimentos
    └── Movimentos Financeiros
```

## Mapeamento de Dependências por Categoria

### CATEGORIA: Dados Mestres (Cadastros Base)

#### 1. Empresas/Filiais
**Endpoint:** `GET /INTEGRACAO/EMPRESAS`
- **Dependências:** Nenhuma (endpoint base)
- **Retorna:** Lista de empresas com códigos
- **Usado por:** Praticamente todos os outros endpoints
- **Campos importantes:**
  - `codigo` - ID da empresa
  - `razaoSocial` - Nome da empresa
  - `cnpj` - CNPJ da empresa

#### 2. Produtos
**Endpoint:** `GET /INTEGRACAO/PRODUTO`
- **Dependências:**
  - `/INTEGRACAO/EMPRESAS` (para filtrar por empresa)
  - `/INTEGRACAO/GRUPO` (opcional, para filtrar por grupo)
- **Retorna:** Lista de produtos com códigos
- **Usado por:**
  - `/INTEGRACAO/RELATORIO/VENDA_PERIODO` (parâmetro `produto`)
  - `/INTEGRACAO/PRODUTO_ESTOQUE`
  - `/INTEGRACAO/VENDA_ITEM`
- **Campos importantes:**
  - `codigo` - ID do produto
  - `descricao` - Nome do produto
  - `tipo` - Tipo do produto (COMBUSTIVEL, PRODUTO, etc)
  - `codigoExterno` - Código externo/referência

**Endpoint Relacionado:** `GET /INTEGRACAO/PRODUTO_EMPRESA`
- **Uso:** Obter produtos específicos de uma empresa
- **Dependências:** `/INTEGRACAO/EMPRESAS`

#### 3. Grupos de Produto
**Endpoint:** `GET /INTEGRACAO/GRUPO`
- **Dependências:** Nenhuma
- **Retorna:** Lista de grupos de produtos
- **Usado por:**
  - `/INTEGRACAO/PRODUTO` (filtro)
  - `/INTEGRACAO/RELATORIO/VENDA_PERIODO` (parâmetro `grupoProduto`)

#### 4. Clientes
**Endpoint:** `GET /INTEGRACAO/CLIENTE`
- **Dependências:**
  - `/INTEGRACAO/EMPRESAS` (para filtrar por empresa)
- **Parâmetros importantes:**
  - `empresaCodigo` - Filtrar por empresa
  - `clienteCodigo` - Buscar cliente específico
  - `clienteCodigoExterno` - Buscar por código externo
- **Retorna:** Lista de clientes com códigos
- **Usado por:**
  - `/INTEGRACAO/RELATORIO/VENDA_PERIODO` (parâmetro `cliente`)
  - `/INTEGRACAO/VENDA`
  - `/INTEGRACAO/CONSUMO_CLIENTE`

**Endpoint Relacionado:** `GET /INTEGRACAO/CLIENTE_EMPRESA`
- **Uso:** Obter clientes vinculados a empresas específicas
- **Dependências:** `/INTEGRACAO/EMPRESAS`

#### 5. Grupos de Cliente
**Endpoint:** `GET /INTEGRACAO/GRUPO_CLIENTE`
- **Dependências:** Nenhuma
- **Retorna:** Lista de grupos de clientes
- **Usado por:**
  - `/INTEGRACAO/RELATORIO/VENDA_PERIODO` (parâmetro `grupoCliente`)

#### 6. Funcionários
**Endpoint:** `GET /INTEGRACAO/FUNCIONARIO`
- **Dependências:**
  - `/INTEGRACAO/EMPRESAS` (para filtrar por empresa)
- **Retorna:** Lista de funcionários com códigos
- **Usado por:**
  - `/INTEGRACAO/RELATORIO/VENDA_PERIODO` (parâmetro `funcionario`)
  - `/INTEGRACAO/RELATORIO/PRODUTIVIDADE_FUNCIONARIO`

### CATEGORIA: Equipamentos (Combustível)

#### 7. Bombas
**Endpoint:** `GET /INTEGRACAO/BOMBA`
- **Dependências:**
  - `/INTEGRACAO/EMPRESAS` (parâmetro `empresaCodigo`)
- **Retorna:** Lista de bombas de combustível
- **Usado por:**
  - `/INTEGRACAO/BICO` (relacionamento bomba-bico)
- **Campos importantes:**
  - `codigo` - ID da bomba
  - `descricao` - Descrição da bomba
  - `ilha` - Número da ilha

#### 8. Bicos
**Endpoint:** `GET /INTEGRACAO/BICO`
- **Dependências:**
  - `/INTEGRACAO/EMPRESAS` (parâmetro `empresaCodigo`)
  - `/INTEGRACAO/BOMBA` (relacionamento)
- **Retorna:** Lista de bicos de abastecimento
- **Usado por:**
  - `/INTEGRACAO/ABASTECIMENTO` (relacionamento)
- **Campos importantes:**
  - `codigo` - ID do bico
  - `bombaCodigo` - ID da bomba relacionada
  - `produtoCodigo` - ID do produto combustível

#### 9. Tanques
**Endpoint:** `GET /INTEGRACAO/TANQUE`
- **Dependências:**
  - `/INTEGRACAO/EMPRESAS` (implícito)
- **Retorna:** Lista de tanques de combustível
- **Campos importantes:**
  - `codigo` - ID do tanque
  - `descricao` - Descrição do tanque
  - `capacidade` - Capacidade em litros
  - `estoqueAtual` - Estoque atual

#### 10. PDV/Caixa
**Endpoint:** `GET /INTEGRACAO/PDV`
- **Dependências:**
  - `/INTEGRACAO/EMPRESAS` (parâmetro `empresaCodigo`)
- **Retorna:** Lista de PDVs/Caixas
- **Usado por:**
  - `/INTEGRACAO/RELATORIO/VENDA_PERIODO` (parâmetros `pdvCaixa`, `pdvGerouVenda`)
  - `/INTEGRACAO/CAIXA`

### CATEGORIA: Estoque

#### 11. Estoque
**Endpoint:** `GET /INTEGRACAO/ESTOQUE`
- **Dependências:**
  - `/INTEGRACAO/EMPRESAS`
  - `/INTEGRACAO/PRODUTO` (para filtrar por produto)
- **Retorna:** Informações de estoque
- **Usado por:**
  - `/INTEGRACAO/RELATORIO/VENDA_PERIODO` (parâmetro `estoque`)

**Endpoint Relacionado:** `GET /INTEGRACAO/PRODUTO_ESTOQUE`
- **Uso:** Estoque específico por produto
- **Dependências:** `/INTEGRACAO/PRODUTO`

### CATEGORIA: Financeiro

#### 12. Prazos
**Endpoint:** `GET /INTEGRACAO/PRAZOS`
- **Dependências:** Nenhuma
- **Retorna:** Lista de prazos de pagamento
- **Usado por:**
  - `/INTEGRACAO/RELATORIO/VENDA_PERIODO` (parâmetro `prazo`)
  - `/INTEGRACAO/TABELA_PRECO_PRAZO`

#### 13. Formas de Pagamento
**Endpoint:** `GET /INTEGRACAO/FORMA_PAGAMENTO`
- **Dependências:** Nenhuma
- **Retorna:** Lista de formas de pagamento
- **Usado por:**
  - `/INTEGRACAO/VENDA_FORMA_PAGAMENTO`

#### 14. Centro de Custo
**Endpoint:** `GET /INTEGRACAO/CENTRO_CUSTO`
- **Dependências:** Nenhuma
- **Retorna:** Lista de centros de custo
- **Usado por:**
  - `/INTEGRACAO/RELATORIO/VENDA_PERIODO` (parâmetro `centroCusto`)

### CATEGORIA: Transações (Vendas e Abastecimentos)

#### 15. Vendas
**Endpoint:** `GET /INTEGRACAO/VENDA`
- **Dependências:**
  - `/INTEGRACAO/EMPRESAS` (parâmetro `empresaCodigo`)
  - `/INTEGRACAO/CLIENTE` (opcional, para filtrar por cliente)
- **Retorna:** Lista de vendas
- **Relacionamentos:**
  - `/INTEGRACAO/VENDA_ITEM` - Itens da venda
  - `/INTEGRACAO/VENDA_FORMA_PAGAMENTO` - Formas de pagamento
  - `/INTEGRACAO/ABASTECIMENTO` - Abastecimentos vinculados

#### 16. Itens de Venda
**Endpoint:** `GET /INTEGRACAO/VENDA_ITEM`
- **Dependências:**
  - `/INTEGRACAO/VENDA` (para obter vendaCodigo)
  - `/INTEGRACAO/PRODUTO` (relacionamento)
- **Retorna:** Itens das vendas com detalhes

#### 17. Abastecimentos
**Endpoint:** `GET /INTEGRACAO/ABASTECIMENTO`
- **Dependências:**
  - `/INTEGRACAO/EMPRESAS` (parâmetro `empresaCodigo`)
  - `/INTEGRACAO/BICO` (relacionamento)
  - `/INTEGRACAO/VENDA_ITEM` (vinculação obrigatória)
- **Retorna:** Dados de abastecimentos
- **Observação:** Todo abastecimento está vinculado a um item de venda

### CATEGORIA: Relatórios

#### 18. Relatório de Vendas por Período
**Endpoint:** `GET /INTEGRACAO/RELATORIO/VENDA_PERIODO`
- **Dependências múltiplas:**
  - `/INTEGRACAO/EMPRESAS` → parâmetro `filial`
  - `/INTEGRACAO/PRODUTO` → parâmetro `produto`
  - `/INTEGRACAO/CLIENTE` → parâmetro `cliente`
  - `/INTEGRACAO/FUNCIONARIO` → parâmetro `funcionario`
  - `/INTEGRACAO/GRUPO` → parâmetro `grupoProduto`
  - `/INTEGRACAO/GRUPO_CLIENTE` → parâmetro `grupoCliente`
  - `/INTEGRACAO/PRAZOS` → parâmetro `prazo`
  - `/INTEGRACAO/PDV` → parâmetros `pdvCaixa`, `pdvGerouVenda`
  - `/INTEGRACAO/ESTOQUE` → parâmetro `estoque`
  - `/INTEGRACAO/CENTRO_CUSTO` → parâmetro `centroCusto`
- **Observação:** Este é um dos endpoints mais complexos, com múltiplas dependências

## Fluxos de Uso Comuns

### Fluxo 1: Consultar Vendas de um Produto Específico

```
1. GET /INTEGRACAO/EMPRESAS
   → Obter lista de empresas
   → Selecionar empresaCodigo desejado

2. GET /INTEGRACAO/PRODUTO?empresaCodigo={empresaCodigo}
   → Obter lista de produtos da empresa
   → Selecionar produtoCodigo desejado

3. GET /INTEGRACAO/RELATORIO/VENDA_PERIODO
   Parâmetros:
   - dataInicial: "2025-01-01"
   - dataFinal: "2025-01-31"
   - tipoData: "FISCAL"
   - ordenacaoPor: "QUANTIDADE_VENDIDA"
   - cupomCancelado: false
   - filial: [empresaCodigo]
   - produto: [produtoCodigo]
   - agrupamentoPor: "PRODUTO"
```

### Fluxo 2: Consultar Vendas de Combustível por Bico

```
1. GET /INTEGRACAO/EMPRESAS
   → Obter empresaCodigo

2. GET /INTEGRACAO/BOMBA?empresaCodigo={empresaCodigo}
   → Obter lista de bombas
   → Selecionar bombaCodigo

3. GET /INTEGRACAO/BICO?empresaCodigo={empresaCodigo}
   → Filtrar bicos da bomba desejada
   → Obter bicoCodigo

4. GET /INTEGRACAO/ABASTECIMENTO?empresaCodigo={empresaCodigo}&bicoCodigo={bicoCodigo}
   → Obter abastecimentos do bico específico
```

### Fluxo 3: Consultar Vendas por Cliente

```
1. GET /INTEGRACAO/EMPRESAS
   → Obter empresaCodigo

2. GET /INTEGRACAO/CLIENTE?empresaCodigo={empresaCodigo}
   → Obter lista de clientes
   → Selecionar clienteCodigo

3. GET /INTEGRACAO/RELATORIO/VENDA_PERIODO
   Parâmetros:
   - dataInicial: "2025-01-01"
   - dataFinal: "2025-01-31"
   - tipoData: "FISCAL"
   - ordenacaoPor: "QUANTIDADE_VENDIDA"
   - cupomCancelado: false
   - filial: [empresaCodigo]
   - cliente: clienteCodigo
   - agrupamentoPor: "CLIENTE"
```

### Fluxo 4: Análise de Vendas por Grupo de Produto

```
1. GET /INTEGRACAO/EMPRESAS
   → Obter empresaCodigo

2. GET /INTEGRACAO/GRUPO
   → Obter lista de grupos de produto
   → Selecionar grupoCodigo

3. GET /INTEGRACAO/RELATORIO/VENDA_PERIODO
   Parâmetros:
   - dataInicial: "2025-01-01"
   - dataFinal: "2025-01-31"
   - tipoData: "FISCAL"
   - ordenacaoPor: "PARTICIPACAO"
   - cupomCancelado: false
   - filial: [empresaCodigo]
   - grupoProduto: [grupoCodigo]
   - agrupamentoPor: "GRUPO_PRODUTO"
```

### Fluxo 5: Relatório de Combustíveis vs Conveniência

```
1. GET /INTEGRACAO/EMPRESAS
   → Obter empresaCodigo

2. GET /INTEGRACAO/RELATORIO/VENDA_PERIODO (Combustíveis)
   Parâmetros:
   - dataInicial: "2025-01-01"
   - dataFinal: "2025-01-31"
   - tipoData: "FISCAL"
   - ordenacaoPor: "QUANTIDADE_VENDIDA"
   - cupomCancelado: false
   - filial: [empresaCodigo]
   - tipoProduto: ["COMBUSTIVEL"]
   - deptoSelcon: "PISTA"

3. GET /INTEGRACAO/RELATORIO/VENDA_PERIODO (Conveniência)
   Parâmetros:
   - dataInicial: "2025-01-01"
   - dataFinal: "2025-01-31"
   - tipoData: "FISCAL"
   - ordenacaoPor: "QUANTIDADE_VENDIDA"
   - cupomCancelado: false
   - filial: [empresaCodigo]
   - deptoSelcon: "LOJA"
```

### Fluxo 6: Consultar Estoque de Produtos

```
1. GET /INTEGRACAO/EMPRESAS
   → Obter empresaCodigo

2. GET /INTEGRACAO/PRODUTO?empresaCodigo={empresaCodigo}
   → Obter lista de produtos

3. GET /INTEGRACAO/PRODUTO_ESTOQUE?empresaCodigo={empresaCodigo}&produtoCodigo={produtoCodigo}
   → Obter estoque específico do produto
```

### Fluxo 7: Consultar Produtividade de Funcionário

```
1. GET /INTEGRACAO/EMPRESAS
   → Obter empresaCodigo

2. GET /INTEGRACAO/FUNCIONARIO?empresaCodigo={empresaCodigo}
   → Obter lista de funcionários
   → Selecionar funcionarioCodigo

3. GET /INTEGRACAO/RELATORIO/PRODUTIVIDADE_FUNCIONARIO
   Parâmetros:
   - dataInicial: "2025-01-01"
   - dataFinal: "2025-01-31"
   - empresaCodigo: empresaCodigo
   - funcionario: [funcionarioCodigo]
```

## Regras Importantes para Agentes de IA

### 1. Sempre Começar com Empresas
Antes de qualquer consulta que necessite filtrar por empresa/filial, **sempre** consultar `/INTEGRACAO/EMPRESAS` primeiro.

### 2. Validar IDs Antes de Usar
Nunca assumir que um ID existe. Sempre consultar o endpoint correspondente para obter a lista de IDs válidos.

### 3. Respeitar Tipos de Dados
- **Datas:** Formato YYYY-MM-DD (ex: "2025-01-07")
- **Arrays:** Quando um parâmetro aceita array, passar múltiplos valores
- **Enums:** Usar exatamente os valores especificados (case-sensitive)

### 4. Entender Relacionamentos
- **Bomba → Bico:** Uma bomba tem múltiplos bicos
- **Bico → Produto:** Cada bico está associado a um produto combustível
- **Venda → Venda Item → Abastecimento:** Hierarquia de vendas
- **Produto → Produto Unidade Negócio:** Produtos são compartilhados, mas preços/estoque são por unidade

### 5. Usar Filtros Apropriados
- **tipoProduto:** Usar para diferenciar combustíveis de outros produtos
- **deptoSelcon:** Usar para separar pista (combustível) de loja (conveniência)
- **tipoData:** FISCAL para relatórios oficiais, MOVIMENTO para operacional

### 6. Considerar Performance
- Períodos muito longos podem impactar performance
- Usar `limite` e `ultimoCodigo` para paginação quando disponível
- Filtrar o máximo possível para reduzir volume de dados

## Endpoints que NÃO Requerem Dependências

Estes endpoints podem ser consultados diretamente sem necessidade de consultas prévias:

1. `/INTEGRACAO/EMPRESAS` - Base de tudo
2. `/INTEGRACAO/GRUPO` - Grupos de produto
3. `/INTEGRACAO/GRUPO_CLIENTE` - Grupos de cliente
4. `/INTEGRACAO/PRAZOS` - Prazos de pagamento
5. `/INTEGRACAO/FORMA_PAGAMENTO` - Formas de pagamento
6. `/INTEGRACAO/CENTRO_CUSTO` - Centros de custo
7. `/INTEGRACAO/FUNCOES` - Funções do sistema

## Tabela de Referência Rápida

| Endpoint | Dependências | Retorna | Usado Por |
|----------|--------------|---------|-----------|
| `/EMPRESAS` | Nenhuma | Lista de empresas | Quase todos |
| `/PRODUTO` | EMPRESAS | Lista de produtos | VENDA_PERIODO, VENDA_ITEM |
| `/CLIENTE` | EMPRESAS | Lista de clientes | VENDA_PERIODO, VENDA |
| `/FUNCIONARIO` | EMPRESAS | Lista de funcionários | VENDA_PERIODO, PRODUTIVIDADE |
| `/BOMBA` | EMPRESAS | Lista de bombas | BICO |
| `/BICO` | EMPRESAS, BOMBA | Lista de bicos | ABASTECIMENTO |
| `/PDV` | EMPRESAS | Lista de PDVs | VENDA_PERIODO, CAIXA |
| `/GRUPO` | Nenhuma | Grupos de produto | PRODUTO, VENDA_PERIODO |
| `/GRUPO_CLIENTE` | Nenhuma | Grupos de cliente | VENDA_PERIODO |
| `/PRAZOS` | Nenhuma | Prazos de pagamento | VENDA_PERIODO |
| `/ESTOQUE` | EMPRESAS, PRODUTO | Dados de estoque | VENDA_PERIODO |
| `/CENTRO_CUSTO` | Nenhuma | Centros de custo | VENDA_PERIODO |

## Conclusão

Este mapeamento de dependências é fundamental para o uso correto da API WebPosto. Agentes de IA devem seguir os fluxos documentados para garantir que todas as informações necessárias sejam obtidas antes de fazer consultas complexas.

A regra de ouro é: **Se um parâmetro requer um ID, sempre consulte o endpoint correspondente primeiro para obter a lista de IDs válidos.**
