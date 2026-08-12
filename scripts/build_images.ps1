param(
    [string]$ProjectId = "ceo-dev123",
    [string]$Region = "us-central1",
    [string]$Repository = "ceosystem",
    [string]$GatewayServiceName = "ceoagent-gateway",
    [string]$WorkerServiceName = "ceoagent-persistence-worker",
    [string]$BillingApiServiceName = "ceoagent-billing-api",
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
$billingApiImage = "$Region-docker.pkg.dev/$ProjectId/$Repository/$BillingApiServiceName`:$Tag"

Write-Host "Building gateway image: $gatewayImage"
docker build -f services/agent_gateway/Dockerfile -t $gatewayImage .

Write-Host "Pushing gateway image: $gatewayImage"
docker push $gatewayImage

Write-Host "Building worker image: $workerImage"
docker build -f services/agent_persistence_worker/Dockerfile -t $workerImage .

Write-Host "Pushing worker image: $workerImage"
docker push $workerImage

Write-Host "Building Billing API image: $billingApiImage"
docker build -f services/billing_api/Dockerfile -t $billingApiImage .

Write-Host "Pushing Billing API image: $billingApiImage"
docker push $billingApiImage

[pscustomobject]@{
    gateway_image     = $gatewayImage
    worker_image      = $workerImage
    billing_api_image = $billingApiImage
}
