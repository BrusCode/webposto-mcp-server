# WebPosto MCP Server - Quality Automação

![Quality Automação](https://www.webposto.com.br/assets/logos/webposto/logo-wp.webp)

**Versão:** 1.1.0

**Licença:** MIT

**Autor:** Quality Automação

---

## Sumário

- [Visão Geral](#visão-geral)
- [Recursos](#recursos)
- [Arquitetura](#arquitetura)
- [Autenticação](#autenticação)
- [Instalação e Configuração](#instalação-e-configuração)
  - [Pré-requisitos](#pré-requisitos)
  - [Opção 1: Docker (Recomendado)](#opção-1-docker-recomendado)
  - [Opção 2: WSL ou Linux](#opção-2-wsl-ou-linux)
  - [Opção 3: Windows Nativo (PowerShell)](#opção-3-windows-nativo-powershell)
- [Uso](#uso)
- [Exemplos de Requisições](#exemplos-de-requisições)
- [Deploy em Nuvem (AWS Serverless)](#deploy-em-nuvem-aws-serverless)
- [Desenvolvimento](#desenvolvimento)
- [Licença](#licença)

---

## Visão Geral

O **WebPosto MCP Server** é um servidor MCP (Model Context Protocol) robusto e completo, projetado para integrar assistentes de Inteligência Artificial com o sistema de gestão de postos de combustível **WebPosto**, da Quality Automação. Ele expõe toda a gama de funcionalidades da API do WebPosto como ferramentas (tools) que podem ser consumidas por modelos de linguagem, permitindo a automação de tarefas, consultas complexas e operações diretamente no sistema.

Este projeto foi desenvolvido seguindo as melhores práticas de engenharia de software, com foco em escalabilidade, segurança e facilidade de manutenção. O servidor é totalmente containerizado com Docker e preparado para deploy em ambientes locais, on-premises ou em nuvem (AWS Serverless).

## Recursos

- **Cobertura Completa da API:** **144 ferramentas MCP** geradas automaticamente a partir da especificação OpenAPI 3.1.0 do WebPosto, cobrindo 100% dos endpoints disponíveis.
- **Arquitetura Modular:** Código organizado em módulos de configuração, cliente de API e ferramentas, facilitando a manutenção e extensão.
- **Pronto para Produção:** Containerização com Docker e Docker Compose para um deploy rápido e consistente.
- **Múltiplas Opções de Instalação:** Suporte para Docker, WSL/Linux e Windows nativo.
- **Deploy em Nuvem:** Inclui um template AWS SAM (Serverless Application Model) para deploy da aplicação como uma função Lambda com API Gateway.
- **Segurança:** Utiliza usuários não-root nos containers e segue as melhores práticas de gerenciamento de credenciais via variáveis de ambiente.

## Arquitetura

O servidor é construído em Python 3.11 com base no SDK do **MCP**:

```
webposto-mcp-server/
├── aws/                          # Infraestrutura AWS (SAM)
│   └── template.yaml
├── scripts/                      # Scripts de inicialização
│   ├── start_server.ps1          # Windows PowerShell
│   └── start_server.sh           # Linux/WSL/macOS
├── src/                          # Código fonte
│   ├── api/                      # Cliente HTTP
│   │   └── webposto_client.py
│   ├── tools/                    # Ferramentas MCP modulares
│   ├── config.py                 # Configuração via env vars
│   ├── lambda_handler.py         # Handler AWS Lambda
│   └── server.py                 # Servidor MCP principal
├── tests/                        # Testes automatizados
├── .env.example                  # Template de configuração
├── Dockerfile                    # Containerização
├── docker-compose.yml            # Orquestração de containers
└── README.md
```

---

## Autenticação

A API do WebPosto utiliza autenticação via **parâmetro `chave` na query string** de cada requisição. Este é o formato oficial conforme documentação da API.

### Exemplo de Requisição

```bash
curl --request GET \
  --url 'https://web.qualityautomacao.com.br/INTEGRACAO/VENDA_RESUMO?dataInicial=2025-12-18&dataFinal=2025-12-18&situacao=A&chave=SUA_CHAVE_AQUI&empresaCodigo=7' \
  --header 'Accept: application/json'
```

### Configuração da Chave

A chave de API deve ser configurada na variável de ambiente `WEBPOSTO_API_KEY`:

```bash
# Linux/WSL/macOS
export WEBPOSTO_API_KEY="sua-chave-aqui"

# Windows PowerShell
$env:WEBPOSTO_API_KEY="sua-chave-aqui"
```

Ou no arquivo `.env`:

```env
WEBPOSTO_API_KEY=sua-chave-aqui
```

---

## Instalação e Configuração

### Pré-requisitos

- **Git:** Para clonar o repositório.
- **Chave de API do WebPosto:** Obtenha sua chave no painel administrativo do WebPosto.

### Opção 1: Docker (Recomendado)

Este é o método mais simples e recomendado, pois isola todas as dependências.

1. **Instale Docker e Docker Compose:**
   - [Instruções para Docker](https://docs.docker.com/get-docker/)
   - [Instruções para Docker Compose](https://docs.docker.com/compose/install/)

2. **Clone o repositório:**
   ```bash
   git clone https://github.com/BrusCode/webposto-mcp-server.git
   cd webposto-mcp-server
   ```

3. **Configure as variáveis de ambiente:**
   ```bash
   cp .env.example .env
   # Edite o arquivo .env com seu editor preferido
   # Substitua SUA_CHAVE_AQUI pela sua chave de API
   ```

4. **Inicie o servidor:**
   ```bash
   docker-compose up -d
   ```

Para verificar os logs: `docker-compose logs -f`

### Opção 2: WSL ou Linux

1. **Instale o Python 3.10 ou superior.**

2. **Clone o repositório:**
   ```bash
   git clone https://github.com/BrusCode/webposto-mcp-server.git
   cd webposto-mcp-server
   ```

3. **Configure as variáveis de ambiente:**
   ```bash
   cp .env.example .env
   nano .env  # ou seu editor preferido
   ```

4. **Execute o script de inicialização:**
   ```bash
   chmod +x scripts/start_server.sh
   ./scripts/start_server.sh
   ```

### Opção 3: Windows Nativo (PowerShell)

1. **Instale Python 3.10 ou superior** do [site oficial](https://www.python.org/downloads/windows/) (marque "Add Python to PATH").

2. **Clone o repositório:**
   ```powershell
   git clone https://github.com/BrusCode/webposto-mcp-server.git
   cd webposto-mcp-server
   ```

3. **Configure as variáveis de ambiente:**
   ```powershell
   Copy-Item .env.example .env
   notepad .env  # Edite e insira sua chave
   ```

4. **Execute o script de inicialização:**
   ```powershell
   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
   .\scripts\start_server.ps1
   ```

---

## Uso

Após a inicialização, o servidor MCP estará pronto para receber conexões. Configure seu cliente MCP (como Claude Desktop ou Manus) para se conectar ao servidor.

### Configuração no Claude Desktop

Adicione ao arquivo de configuração do Claude Desktop (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "webposto": {
      "command": "python",
      "args": ["-m", "src.server"],
      "cwd": "/caminho/para/webposto-mcp-server",
      "env": {
        "WEBPOSTO_API_KEY": "sua-chave-aqui"
      }
    }
  }
}
```

---

## Exemplos de Requisições

### Consultar Vendas do Dia

```
Ferramenta: consultar_venda
Parâmetros:
  - data_inicial: "2025-12-18"
  - data_final: "2025-12-18"
```

### Consultar Resumo de Vendas

```
Ferramenta: consultar_venda_resumo
Parâmetros:
  - data_inicial: "2025-12-18"
  - data_final: "2025-12-18"
  - situacao: "A"
  - empresa_codigo: 7
```

### Consultar Abastecimentos

```
Ferramenta: consultar_abastecimento
Parâmetros:
  - data_inicial: "2025-12-18"
  - data_final: "2025-12-18"
```

### Consultar Estoque

```
Ferramenta: consultar_estoque_periodo
Parâmetros:
  - data_final: "2025-12-18"
```

---

## Deploy em Nuvem (AWS Serverless)

O projeto está preparado para deploy na AWS como uma aplicação serverless.

### Pré-requisitos

- [Conta na AWS](https://aws.amazon.com/)
- [AWS CLI](https://aws.amazon.com/cli/) configurada
- [AWS SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-install.html)
- Docker (para o build do SAM)

### Passos para o Deploy

1. **Build do Projeto:**
   ```bash
   sam build --use-container
   ```

2. **Deploy Guiado:**
   ```bash
   sam deploy --guided
   ```

Após o deploy, o SAM fornecerá o endpoint do API Gateway.

---

## Desenvolvimento

### Estrutura do Código

- `src/server.py`: Servidor MCP principal com todas as ferramentas
- `src/api/webposto_client.py`: Cliente HTTP para a API WebPosto
- `src/config.py`: Configuração via variáveis de ambiente

### Executar Testes

```bash
pytest tests/ -v
```

### Linting e Formatação

```bash
black src/
isort src/
ruff check src/
```

---

## Licença

Este projeto está licenciado sob a **Licença MIT**. Veja o arquivo [LICENSE](LICENSE) para mais detalhes.

---

**Quality Automação** - Sistema de Gestão de Postos WebPosto
