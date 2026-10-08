<#
.SYNOPSIS  Deploys infrastructure + code to Azure and uploads your resume.
.EXAMPLE   ./scripts/deploy.ps1 -ResourceGroup jobbot-rg -EmailTo me@example.com -ResumePath C:\resume.pdf -AdzunaAppId xxx -AdzunaAppKey yyy
#>
param(
    [Parameter(Mandatory)] [string] $ResourceGroup,
    [Parameter(Mandatory)] [string] $EmailTo,
    [Parameter(Mandatory)] [string] $ResumePath,
    [string] $Location = 'eastus2',
    [string] $AdzunaAppId = '',
    [string] $AdzunaAppKey = '',
    [string] $JobPreferences = ''
)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent

az group create -n $ResourceGroup -l $Location | Out-Null
$out = az deployment group create -g $ResourceGroup -f "$root/infra/main.bicep" `
    --parameters emailTo=$EmailTo adzunaAppId=$AdzunaAppId adzunaAppKey=$AdzunaAppKey jobPreferences=$JobPreferences `
    --query properties.outputs -o json | ConvertFrom-Json
if ($LASTEXITCODE -ne 0) { throw 'Bicep deployment failed' }

$func = $out.functionAppName.value
$storage = $out.storageAccountName.value

# Upload resume (named resume.<ext>)
$ext = [IO.Path]::GetExtension($ResumePath)
$key = az storage account keys list -g $ResourceGroup -n $storage --query '[0].value' -o tsv
az storage container create -n jobbot --account-name $storage --account-key $key | Out-Null
az storage blob upload -c jobbot -n "resume$ext" -f $ResumePath --account-name $storage --account-key $key --overwrite | Out-Null

$zip = Join-Path ([IO.Path]::GetTempPath()) 'jobbot.zip'
if (Test-Path $zip) { Remove-Item $zip }
& "$PSScriptRoot/make-zip.ps1" -Root $root -Destination $zip
az functionapp deployment source config-zip -g $ResourceGroup -n $func --src $zip --build-remote true --timeout 600
if ($LASTEXITCODE -ne 0) { throw 'Code deployment failed' }
Remove-Item $zip

Write-Host "Deployed. Function app: $func"
Write-Host "Trigger a test run: az functionapp function keys list / invoke https://$func.azurewebsites.net/api/run?code=<key>"
