param(
    [string]$ProjectId = "ceo-dev123",
    [string]$Region = "us-central1",
    [string]$Repository = "ceosystem",
    [string]$GatewayServiceName = "ceoagent-gateway",
    [string]$WorkerServiceName = "ceoagent-persistence-worker",
    [string]$Tag = "latest"
)

$ErrorActionPreference = "Stop"

function Require-Command {
    param([string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command '$Name' was not found in PATH."
    }
}

Require-Command docker

$gatewayImage = "$Region-docker.pkg.dev/$ProjectId/$Repository/$GatewayServiceName`:$Tag"
$workerImage = "$Region-docker.pkg.dev/$ProjectId/$Repository/$WorkerServiceName`:$Tag"

Write-Host "Building gateway image: $gatewayImage"
docker build -f services/agent_gateway/Dockerfile -t $gatewayImage .

Write-Host "Pushing gateway image: $gatewayImage"
docker push $gatewayImage

Write-Host "Building worker image: $workerImage"
docker build -f services/agent_persistence_worker/Dockerfile -t $workerImage .

Write-Host "Pushing worker image: $workerImage"
docker push $workerImage

[pscustomobject]@{
    gateway_image = $gatewayImage
    worker_image  = $workerImage
}
