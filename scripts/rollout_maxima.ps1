param(
    [Parameter(Mandatory = $true)]
    [string]$AuthToken,

    [Parameter(Mandatory = $true)]
    [string[]]$AllowedOrigins,

    [string]$ProjectId = "ceo-dev123",
    [string]$Region = "us-central1",
    [string]$Repository = "ceosystem",
    [string]$Tag = "latest",
    [string]$SmokeMessage = "Hello from the new Maxima gateway",
    [switch]$SkipBuild,
    [switch]$SkipApply
)

$ErrorActionPreference = "Stop"

$buildScript = Join-Path $PSScriptRoot "build_images.ps1"
$deployScript = Join-Path $PSScriptRoot "deploy_infra.ps1"
$smokeScript = Join-Path $PSScriptRoot "smoke_gateway.ps1"
$terraformDir = Join-Path $PSScriptRoot "..\\infra\\terraform"

if ($SkipBuild) {
    $gatewayImage = "$Region-docker.pkg.dev/$ProjectId/$Repository/ceoagent-gateway`:$Tag"
    $workerImage = "$Region-docker.pkg.dev/$ProjectId/$Repository/ceoagent-persistence-worker`:$Tag"
}
else {
    $buildResult = & $buildScript `
        -ProjectId $ProjectId `
        -Region $Region `
        -Repository $Repository `
        -Tag $Tag
    $gatewayImage = $buildResult.gateway_image
    $workerImage = $buildResult.worker_image
}

& $deployScript `
    -GatewayImage $gatewayImage `
    -WorkerImage $workerImage `
    -ProjectId $ProjectId `
    -Region $Region `
    -AllowedOrigins $AllowedOrigins `
    -PlanOnly:$SkipApply

if ($SkipApply) {
    Write-Host "Plan-only mode finished. Skipping smoke tests."
    exit 0
}

Push-Location $terraformDir
try {
    $gatewayUrl = terraform output -raw gateway_url
}
finally {
    Pop-Location
}

Write-Host "Running buffered smoke test against $gatewayUrl"
& $smokeScript `
    -ServiceUrl $gatewayUrl `
    -AuthToken $AuthToken `
    -Message $SmokeMessage

Write-Host "Running streaming smoke test against $gatewayUrl"
& $smokeScript `
    -ServiceUrl $gatewayUrl `
    -AuthToken $AuthToken `
    -Message $SmokeMessage `
    -Stream
