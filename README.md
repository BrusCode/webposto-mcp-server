# WebPosto MCP Server - Quality Automação

![Quality Automação](https://www.qualityautomacao.com.br/assets/img/logo.png)

**Versão:** 1.0.0

**Licença:** MIT

**Autor:** Quality Automação & Manus AI

---

## Sumário

- [Visão Geral](#visão-geral)
- [Recursos](#recursos)
- [Arquitetura](#arquitetura)
- [Instalação e Configuração](#instalação-e-configuração)
  - [Pré-requisitos](#pré-requisitos)
  - [Opção 1: Docker (Recomendado)](#opção-1-docker-recomendado)
  - [Opção 2: WSL (Subsistema Windows para Linux) ou Linux](#opção-2-wsl-subsistema-windows-para-linux-ou-linux)
  - [Opção 3: Windows Nativo (PowerShell)](#opção-3-windows-nativo-powershell)
- [Uso](#uso)
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
- **Deploy em Nuvem:** Inclui um template AWS SAM (Serverless Application Model) para deploy da aplicação como uma função Lambda com API Gateway, permitindo uma infraestrutura serverless, escalável e de baixo custo.
- **Segurança:** Utiliza usuários não-root nos containers e segue as melhores práticas de gerenciamento de credenciais via variáveis de ambiente.
- **Documentação Abrangente:** Instruções detalhadas para instalação, configuração e uso em diferentes ambientes.

## Arquitetura

O servidor é construído em Python 3.11 com base no framework **FastAPI** e no SDK do **MCP**. A arquitetura foi desenhada para ser limpa e desacoplada:

```
webposto-mcp-server/
├── aws/                    # Arquivos para deploy serverless na AWS (SAM)
│   └── template.yaml
├── scripts/                # Scripts de inicialização para diferentes S.O.
│   ├── start_server.ps1
│   └── start_server.sh
├── src/                    # Código fonte da aplicação
│   ├── api/                # Módulo do cliente da API WebPosto
│   ├── tools/              # Ferramentas MCP (geradas dinamicamente)
│   ├── config.py           # Configuração e variáveis de ambiente
│   ├── lambda_handler.py   # Ponto de entrada para AWS Lambda
│   └── server.py           # Ponto de entrada principal e lógica do servidor
├── tests/                  # Testes automatizados
├── .dockerignore
├── .env.example            # Exemplo de arquivo de configuração
├── .gitignore
├── Dockerfile              # Define a imagem do container
├── docker-compose.yml      # Orquestração do container
├── LICENSE
├── pyproject.toml          # Configuração do projeto e dependências
└── README.md
```

- **`src/server.py`**: É o coração da aplicação. Ele inicializa o servidor MCP, carrega as ferramentas e define a lógica principal.
- **`src/api/webposto_client.py`**: Implementa um cliente HTTP robusto para se comunicar com a API do WebPosto, gerenciando autenticação, requisições e tratamento de erros.
- **`src/tools/`**: As ferramentas MCP são geradas dinamicamente a partir da especificação da API, garantindo que qualquer atualização na API possa ser rapidamente incorporada ao servidor.
- **`Dockerfile`**: Utiliza um build multi-stage para criar uma imagem Docker otimizada e segura.
- **`aws/template.yaml`**: Define a infraestrutura como código para um deploy serverless na AWS.

---

## Instalação e Configuração

### Pré-requisitos

- **Git:** Para clonar o repositório.
- **Chave de API do WebPosto:** Você precisará de uma chave de API válida para se autenticar.

### Opção 1: Docker (Recomendado)

Este é o método mais simples e recomendado, pois isola todas as dependências.

1.  **Instale Docker e Docker Compose:**
    - [Instruções para Docker](https://docs.docker.com/get-docker/)
    - [Instruções para Docker Compose](https://docs.docker.com/compose/install/)

2.  **Clone o repositório:**
    ```bash
    git clone https://github.com/BrusCode/webposto-mcp-server.git
    cd helion-cloud
    ```

3.  **Configure as variáveis de ambiente:**
    Copie o arquivo de exemplo `.env.example` para `.env` e edite-o, inserindo sua chave de API.
    ```bash
    cp .env.example .env
    # Agora, edite o arquivo .env com seu editor preferido
    # Ex: nano .env
    ```
    Substitua `SUA_API_KEY_AQUI` pela sua chave de API do WebPosto.

4.  **Inicie o servidor:**
    ```bash
    docker-compose up -d
    ```

O servidor MCP estará em execução. Para verificar os logs, use `docker-compose logs -f`.

### Opção 2: WSL (Subsistema Windows para Linux) ou Linux

Este método requer a instalação do Python e das dependências manualmente.

1.  **Instale o Python 3.10 ou superior.**

2.  **Clone o repositório e navegue até a pasta:**
    ```bash
    git clone https://github.com/BrusCode/webposto-mcp-server.git
    cd helion-cloud
    ```

3.  **Configure as variáveis de ambiente:**
    Copie `.env.example` para `.env` e insira sua chave de API, como descrito na seção Docker.
    ```bash
    cp .env.example .env
    nano .env
    ```

4.  **Execute o script de inicialização:**
    O script irá criar um ambiente virtual, instalar as dependências e iniciar o servidor.
    ```bash
    chmod +x scripts/start_server.sh
    ./scripts/start_server.sh
    ```

### Opção 3: Windows Nativo (PowerShell)

1.  **Instale Python 3.10 ou superior** a partir do [site oficial do Python](https://www.python.org/downloads/windows/) (certifique-se de marcar a opção "Add Python to PATH").

2.  **Clone o repositório:**
    ```powershell
    git clone https://github.com/BrusCode/webposto-mcp-server.git
    cd helion-cloud
    ```

3.  **Configure as variáveis de ambiente:**
    Copie `.env.example` para `.env` e insira sua chave de API.
    ```powershell
    Copy-Item .env.example .env
    # Abra o arquivo .env com um editor (ex: notepad .env) e insira sua chave.
    ```

4.  **Execute o script de inicialização:**
    Abra um terminal PowerShell, navegue até a pasta do projeto e execute:
    ```powershell
    # Pode ser necessário ajustar a política de execução de scripts
    Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process

    .\scripts\start_server.ps1
    ```

---

## Uso

Após a inicialização, o servidor MCP estará pronto para receber conexões de um cliente compatível (como o Manus). Configure seu cliente para se conectar ao servidor. Se estiver rodando localmente, o servidor estará disponível via `stdio` ou, se configurado, via HTTP na porta `8000`.

---

## Deploy em Nuvem (AWS Serverless)

O projeto está preparado para deploy na AWS como uma aplicação serverless, o que oferece alta escalabilidade e baixo custo operacional.

### Pré-requisitos

- [Conta na AWS](https://aws.amazon.com/)
- [AWS CLI](https://aws.amazon.com/cli/) configurada
- [AWS SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-install.html)
- Docker (para o build do SAM)

### Passos para o Deploy

1.  **Build do Projeto:**
    ```bash
    sam build --use-container
    ```

2.  **Deploy Guiado:**
    O SAM CLI irá guiar você pelo processo de deploy, solicitando informações como o nome da stack e a chave da API (que será armazenada de forma segura no AWS Secrets Manager).
    ```bash
    sam deploy --guided
    ```

Após o deploy, o SAM fornecerá o endpoint do API Gateway que poderá ser usado para interagir com o servidor MCP.

---

## Desenvolvimento

- **Estrutura do Código:** Siga a estrutura de pastas existente.
- **Dependências:** Adicione novas dependências ao `pyproject.toml` e regenere o `requirements.txt` com `pip-compile` se necessário.
- **Testes:** Crie testes para novas funcionalidades no diretório `tests/` e execute-os com `pytest`.
- **Linting e Formatação:** O projeto usa `black`, `isort` e `ruff` para garantir a qualidade e consistência do código. Use os hooks de pré-commit para automatizar isso.

---

## Licença

Este projeto está licenciado sob a **Licença MIT**. Veja o arquivo [LICENSE](LICENSE) para mais detalhes.
