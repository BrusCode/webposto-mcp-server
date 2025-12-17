# =============================================================================
# WebPosto MCP Server - Script de Inicialização (Windows PowerShell)
# Quality Automação
# =============================================================================

$ErrorActionPreference = "Stop"

# Cores
function Write-ColorOutput($ForegroundColor) {
    $fc = $host.UI.RawUI.ForegroundColor
    $host.UI.RawUI.ForegroundColor = $ForegroundColor
    if ($args) {
        Write-Output $args
    }
    $host.UI.RawUI.ForegroundColor = $fc
}

# Diretórios
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir

Write-Host "========================================" -ForegroundColor Green
Write-Host "  WebPosto MCP Server - Quality Automação" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

# Verificar arquivo .env
$EnvFile = Join-Path $ProjectDir ".env"
$EnvExampleFile = Join-Path $ProjectDir ".env.example"

if (-not (Test-Path $EnvFile)) {
    Write-Host "Arquivo .env não encontrado." -ForegroundColor Yellow
    Write-Host "Criando a partir de .env.example..." -ForegroundColor Yellow
    
    if (Test-Path $EnvExampleFile) {
        Copy-Item $EnvExampleFile $EnvFile
        Write-Host "ATENÇÃO: Configure sua API_KEY no arquivo .env" -ForegroundColor Red
        exit 1
    } else {
        Write-Host "Erro: .env.example não encontrado" -ForegroundColor Red
        exit 1
    }
}

# Carregar variáveis de ambiente
Get-Content $EnvFile | ForEach-Object {
    if ($_ -match "^([^#][^=]+)=(.*)$") {
        $name = $matches[1].Trim()
        $value = $matches[2].Trim()
        [Environment]::SetEnvironmentVariable($name, $value, "Process")
    }
}

# Verificar API_KEY
$ApiKey = [Environment]::GetEnvironmentVariable("WEBPOSTO_API_KEY", "Process")
if ([string]::IsNullOrEmpty($ApiKey) -or $ApiKey -eq "SUA_API_KEY_AQUI") {
    Write-Host "Erro: WEBPOSTO_API_KEY não configurada no arquivo .env" -ForegroundColor Red
    exit 1
}

# Verificar Python
try {
    $PythonVersion = python --version 2>&1
    Write-Host "Python versão: $PythonVersion" -ForegroundColor Green
} catch {
    Write-Host "Erro: Python não encontrado" -ForegroundColor Red
    Write-Host "Instale Python 3.10 ou superior de https://python.org" -ForegroundColor Yellow
    exit 1
}

# Verificar/criar ambiente virtual
$VenvDir = Join-Path $ProjectDir ".venv"
if (-not (Test-Path $VenvDir)) {
    Write-Host "Criando ambiente virtual..." -ForegroundColor Yellow
    python -m venv $VenvDir
}

# Ativar ambiente virtual
$ActivateScript = Join-Path $VenvDir "Scripts\Activate.ps1"
& $ActivateScript

# Instalar dependências
Write-Host "Verificando dependências..." -ForegroundColor Yellow
$RequirementsFile = Join-Path $ProjectDir "requirements.txt"
pip install -q -r $RequirementsFile

# Iniciar servidor
Write-Host ""
Write-Host "Iniciando servidor MCP..." -ForegroundColor Green
$WebpostoUrl = [Environment]::GetEnvironmentVariable("WEBPOSTO_URL", "Process")
if ([string]::IsNullOrEmpty($WebpostoUrl)) {
    $WebpostoUrl = "https://web.qualityautomacao.com.br/INTEGRACAO"
}
Write-Host "URL da API: $WebpostoUrl"
Write-Host ""

Set-Location $ProjectDir
python -m src.server
