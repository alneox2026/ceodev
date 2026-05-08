param(
    [Parameter(Mandatory = $true)]
    [string]$GatewayImage,

    [Parameter(Mandatory = $true)]
    [string]$WorkerImage,

    [string]$ProjectId = "ceo-dev123",
    [string]$Region = "us-central1",
    [string[]]$AllowedOrigins = @("*"),
    [switch]$PlanOnly
)

$ErrorActionPreference = "Stop"

function Require-Command {
    param([string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command '$Name' was not found in PATH."
    }
}

Require-Command terraform

$terraformDir = Join-Path $PSScriptRoot "..\\infra\\terraform"
$varsPath = Join-Path $terraformDir "terraform.auto.tfvars.json"

$payload = @{
    project_id      = $ProjectId
    region          = $Region
    gateway_image   = $GatewayImage
    worker_image    = $WorkerImage
    allowed_origins = $AllowedOrigins
}

$payload | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $varsPath -Encoding UTF8

Push-Location $terraformDir
try {
    terraform init
    terraform plan
    if (-not $PlanOnly) {
        terraform apply -auto-approve
    }
}
finally {
    Pop-Location
}
