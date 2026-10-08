<#
.SYNOPSIS  One-time setup: lets GitHub Actions deploy to the function app using OIDC (no stored passwords).
.EXAMPLE   ./scripts/setup-github-oidc.ps1 -GitHubRepo ivanw/jobbot
#>
param(
    [Parameter(Mandatory)] [string] $GitHubRepo,   # owner/name
    [string] $ResourceGroup = 'jobbot-rg',
    [string] $Branch = 'main'
)
$ErrorActionPreference = 'Stop'

$sub = az account show --query id -o tsv
$tenant = az account show --query tenantId -o tsv
$func = az functionapp list -g $ResourceGroup --query '[0].name' -o tsv
$funcId = az functionapp show -g $ResourceGroup -n $func --query id -o tsv

$appName = 'jobbot-github-deploy'
$clientId = az ad app list --display-name $appName --query '[0].appId' -o tsv
if (-not $clientId) { $clientId = az ad app create --display-name $appName --query appId -o tsv }
if (-not (az ad sp list --filter "appId eq '$clientId'" --query '[0].id' -o tsv)) { az ad sp create --id $clientId | Out-Null }

$cred = @{
    name = 'github-main'; issuer = 'https://token.actions.githubusercontent.com'
    subject = "repo:${GitHubRepo}:ref:refs/heads/$Branch"; audiences = @('api://AzureADTokenExchange')
} | ConvertTo-Json
$tmp = New-TemporaryFile; Set-Content $tmp $cred
if (-not (az ad app federated-credential list --id $clientId --query "[?name=='github-main'].name" -o tsv)) {
    az ad app federated-credential create --id $clientId --parameters "@$tmp" | Out-Null
}
Remove-Item $tmp

# Least privilege: contributor on the function app only
az role assignment create --assignee $clientId --role 'Website Contributor' --scope $funcId | Out-Null

if (Get-Command gh -ErrorAction SilentlyContinue) {
    gh secret set AZURE_CLIENT_ID -R $GitHubRepo -b $clientId
    gh secret set AZURE_TENANT_ID -R $GitHubRepo -b $tenant
    gh secret set AZURE_SUBSCRIPTION_ID -R $GitHubRepo -b $sub
    gh variable set AZURE_RESOURCE_GROUP -R $GitHubRepo -b $ResourceGroup
    gh variable set AZURE_FUNCTIONAPP_NAME -R $GitHubRepo -b $func
    Write-Host 'GitHub secrets/variables set.'
} else {
    Write-Host "gh CLI not found. Add these manually in the repo (Settings > Secrets and variables > Actions):"
    Write-Host "  Secrets:   AZURE_CLIENT_ID=$clientId  AZURE_TENANT_ID=$tenant  AZURE_SUBSCRIPTION_ID=$sub"
    Write-Host "  Variables: AZURE_RESOURCE_GROUP=$ResourceGroup  AZURE_FUNCTIONAPP_NAME=$func"
}
