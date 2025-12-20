# Deploy Serverless na AWS com SAM

Este guia detalha como fazer o deploy do **WebPosto MCP Server** em uma arquitetura serverless na AWS, utilizando o **AWS Serverless Application Model (SAM)**.

## Sumário

- [Visão Geral da Arquitetura](#visão-geral-da-arquitetura)
- [Pré-requisitos](#pré-requisitos)
- [Passo 1: Configurar a Chave da API no Secrets Manager](#passo-1-configurar-a-chave-da-api-no-secrets-manager)
- [Passo 2: Configurar o AWS CLI](#passo-2-configurar-o-aws-cli)
- [Passo 3: Fazer o Build do Projeto](#passo-3-fazer-o-build-do-projeto)
- [Passo 4: Fazer o Deploy da Stack](#passo-4-fazer-o-deploy-da-stack)
- [Passo 5: Testar o Endpoint](#passo-5-testar-o-endpoint)
- [Monitoramento e Logs](#monitoramento-e-logs)
- [Atualização da Stack](#atualização-da-stack)
- [Remoção da Stack](#remoção-da-stack)
- [Análise de Custos](#análise-de-custos)

---

## Visão Geral da Arquitetura

O deploy cria os seguintes recursos na sua conta AWS:

| Recurso | Descrição | Tipo (AWS SAM) |
|---|---|---|
| **API Gateway** | Ponto de entrada HTTP para o servidor. | `AWS::Serverless::HttpApi` |
| **Lambda Function** | Executa o código do servidor MCP. | `AWS::Serverless::Function` |
| **Secrets Manager** | Armazena a chave da API do WebPosto. | (Recurso pré-existente) |
| **CloudWatch Logs** | Armazena os logs da função Lambda. | `AWS::Logs::LogGroup` |
| **IAM Role** | Permissões para a Lambda acessar outros serviços. | (Criado automaticamente) |

Este modelo é altamente escalável, seguro e com custo otimizado, ideal para ambientes de produção.

---

## Arquitetura Serverless
```bash
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Cliente MCP   │────▶│  API Gateway    │────▶│  AWS Lambda     │
│  (Claude, etc)  │     │  (HTTP API v2)  │     │  (Python 3.11)  │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                         │
                        ┌─────────────────┐              │
                        │ Secrets Manager │◀─────────────┤
                        │ (API Key)       │              │
                        └─────────────────┘              │
                                                         ▼
                        ┌─────────────────┐     ┌─────────────────┐
                        │  CloudWatch     │◀────│   WebPosto API  │
                        │  (Logs/Metrics) │     │                 │
                        └─────────────────┘     └─────────────────┘
```

---

## Pré-requisitos

1. **Conta na AWS:** [Crie uma aqui](https://aws.amazon.com/free/).
2. **AWS CLI:** [Instale e configure](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-configure.html) com suas credenciais.
3. **AWS SAM CLI:** [Instale o SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html).
4. **Docker:** [Instale o Docker](https://docs.docker.com/get-docker/), necessário para o build local.
5. **Chave da API WebPosto:** Fornecida pela Quality Automação.

---

## Passo 1: Configurar a Chave da API no Secrets Manager

Por segurança, a chave da API é armazenada no AWS Secrets Manager.

1. **Acesse o AWS Secrets Manager:**
   - Vá para o [Console do Secrets Manager](https://console.aws.amazon.com/secretsmanager/).

2. **Crie um novo Secret:**
   - Clique em **Store a new secret**.
   - **Secret type:** Other type of secret.
   - **Key/value pairs:**
     - **Key:** `WEBPOSTO_API_KEY`
     - **Value:** Cole a sua chave da API do WebPosto.
   - **Encryption key:** Deixe o padrão (`aws/secretsmanager`).
   - Clique em **Next**.

3. **Configure o Secret:**
   - **Secret name:** `webposto/api/key` (ou o nome que você definiu no `template.v2.yaml`).
   - **Description:** `Chave de API para integração com o sistema WebPosto.`
   - Clique em **Next**.

4. **Rotação (Opcional):**
   - Deixe a rotação desabilitada por padrão.
   - Clique em **Next** e depois em **Store**.

---

## Passo 2: Configurar o AWS CLI

Verifique se seu AWS CLI está configurado corretamente:

```bash
aws configure
# AWS Access Key ID [********************]: SEU_ACCESS_KEY
# AWS Secret Access Key [********************]: SEU_SECRET_KEY
# Default region name [us-east-1]: SUA_REGIAO
# Default output format [json]: json
```

Teste a comunicação com a AWS:

```bash
aws sts get-caller-identity
```

---

## Passo 3: Fazer o Build do Projeto

O comando `sam build` compila o código-fonte e as dependências, preparando o pacote para o deploy.

Navegue até a raiz do projeto e execute:

```bash
# Use o template v2 para produção
sam build --template-file aws/template.v2.yaml --use-container
```

- `--template-file`: Especifica o template aprimorado.
- `--use-container`: Realiza o build dentro de um container Docker, garantindo a compatibilidade com o ambiente Lambda.

---

## Passo 4: Fazer o Deploy da Stack

O comando `sam deploy` envia a aplicação para a nuvem.

Execute o deploy em modo guiado na primeira vez:

```bash
sam deploy --guided
```

O SAM CLI fará algumas perguntas:

- **Stack Name:** `webposto-mcp-server` (ou um nome de sua preferência).
- **AWS Region:** `us-east-1` (ou a região de sua preferência).
- **Parameter Environment:** `production`.
- **Parameter WebPostoApiKeySecretName:** `webposto/api/key` (confirme o nome do secret).
- **Confirm changes before deploy:** `y` (recomendado).
- **Allow SAM CLI IAM role creation:** `y`.
- **Disable rollback:** `n`.
- **Save arguments to samconfig.toml:** `y` (para facilitar futuros deploys).

Após a confirmação, o SAM provisionará todos os recursos. Aguarde a conclusão.

---

## Passo 5: Testar o Endpoint

Após o deploy, o SAM exibirá o endpoint da API na seção `Outputs`.

1. **Obtenha o URL do Endpoint:**

   ```bash
   aws cloudformation describe-stacks --stack-name webposto-mcp-server --query "Stacks[0].Outputs[?OutputKey==\'ApiEndpoint\'].OutputValue" --output text
   ```

2. **Teste com `curl`:**

   Substitua `[URL_DO_ENDPOINT]` pelo valor obtido.

   ```bash
   curl --request POST \
     --url [URL_DO_ENDPOINT] \
     --header 'Content-Type: application/json' \
     --data '{
       "jsonrpc": "2.0",
       "id": 1,
       "method": "tools/list",
       "params": {}
     }'
   ```

   A resposta deve ser um JSON com a lista de ferramentas disponíveis.

---

## Monitoramento e Logs

Os logs da função Lambda são enviados para o **Amazon CloudWatch**.

1. **Acesse o CloudWatch:**
   - Vá para o [Console do CloudWatch](https://console.aws.amazon.com/cloudwatch/).

2. **Visualize os Logs:**
   - No menu, clique em **Log groups**.
   - Procure pelo grupo de logs: `/aws/lambda/webposto-mcp-function-production`.
   - Clique no grupo para ver os streams de logs e as mensagens da aplicação.

---

## Atualização da Stack

Para atualizar a aplicação com novas versões do código:

1. **Faça as alterações** no código-fonte.
2. **Execute o build** novamente:
   ```bash
   sam build --template-file aws/template.v2.yaml --use-container
   ```
3. **Execute o deploy** (o SAM usará as configurações salvas no `samconfig.toml`):
   ```bash
   sam deploy
   ```

---

## Remoção da Stack

Para remover todos os recursos criados pelo deploy:

```bash
sam delete --stack-name webposto-mcp-server
```

> **Atenção:** Este comando removerá a API Gateway e a função Lambda. O secret no Secrets Manager **não** será removido.

---

## Análise de Custos

A arquitetura serverless é altamente econômica:

- **API Gateway (HTTP API):** Custa aproximadamente **$1.00 por milhão de requisições**.
- **AWS Lambda:** O [Free Tier da AWS](https://aws.amazon.com/free/) inclui **1 milhão de requisições gratuitas por mês**.
- **Secrets Manager:** Custa **$0.40 por secret por mês**.
- **CloudWatch:** Custos mínimos para armazenamento de logs, geralmente cobertos pelo Free Tier.

Para a maioria dos casos de uso, o custo mensal será extremamente baixo.
