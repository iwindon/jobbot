targetScope = 'resourceGroup'

@description('Base name used to derive resource names')
param baseName string = 'jobbot'
param location string = resourceGroup().location
@description('Region for Azure OpenAI (must support the model)')
param openAiLocation string = 'eastus2'
param openAiModel string = 'gpt-4o-mini'
param openAiModelVersion string = '2024-07-18'
@description('Where the daily digest is sent (separate multiple with ;)')
param emailTo string
param localLocations string = 'Greenville, SC;Spartanburg, SC'
param minScore int = 65
param jobPreferences string = ''
@secure()
param adzunaAppId string = ''
@secure()
param adzunaAppKey string = ''

var suffix = uniqueString(resourceGroup().id)
var storageName = toLower('st${take(replace(baseName, '-', ''), 8)}${suffix}')

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: take(storageName, 24)
  location: location
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: {
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
    supportsHttpsTrafficOnly: true
  }
}

resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: '${baseName}-logs-${suffix}'
  location: location
  properties: { sku: { name: 'PerGB2018' }, retentionInDays: 30 }
}

resource insights 'Microsoft.Insights/components@2020-02-02' = {
  name: '${baseName}-ai-${suffix}'
  location: location
  kind: 'web'
  properties: { Application_Type: 'web', WorkspaceResourceId: logs.id }
}

resource openai 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: '${baseName}-oai-${suffix}'
  location: openAiLocation
  kind: 'OpenAI'
  sku: { name: 'S0' }
  properties: {
    customSubDomainName: '${baseName}-oai-${suffix}'
    publicNetworkAccess: 'Enabled'
  }
}

resource deployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: openai
  name: openAiModel
  sku: { name: 'GlobalStandard', capacity: 30 }
  properties: {
    model: { format: 'OpenAI', name: openAiModel, version: openAiModelVersion }
  }
}

resource emailService 'Microsoft.Communication/emailServices@2023-04-01' = {
  name: '${baseName}-email-${suffix}'
  location: 'global'
  properties: { dataLocation: 'United States' }
}

resource emailDomain 'Microsoft.Communication/emailServices/domains@2023-04-01' = {
  parent: emailService
  name: 'AzureManagedDomain'
  location: 'global'
  properties: { domainManagement: 'AzureManaged' }
}

resource comms 'Microsoft.Communication/communicationServices@2023-04-01' = {
  name: '${baseName}-acs-${suffix}'
  location: 'global'
  properties: { dataLocation: 'United States', linkedDomains: [emailDomain.id] }
}

resource plan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: '${baseName}-plan-${suffix}'
  location: location
  kind: 'linux'
  sku: { name: 'Y1', tier: 'Dynamic' }
  properties: { reserved: true }
}

var storageConn = 'DefaultEndpointsProtocol=https;AccountName=${storage.name};AccountKey=${storage.listKeys().keys[0].value};EndpointSuffix=${environment().suffixes.storage}'

resource func 'Microsoft.Web/sites@2023-12-01' = {
  name: '${baseName}-func-${suffix}'
  location: location
  kind: 'functionapp,linux'
  identity: { type: 'SystemAssigned' }
  properties: {
    serverFarmId: plan.id
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'PYTHON|3.11'
      minTlsVersion: '1.2'
      ftpsState: 'Disabled'
      appSettings: [
        { name: 'AzureWebJobsStorage', value: storageConn }
        { name: 'FUNCTIONS_EXTENSION_VERSION', value: '~4' }
        { name: 'FUNCTIONS_WORKER_RUNTIME', value: 'python' }
        { name: 'SCM_DO_BUILD_DURING_DEPLOYMENT', value: 'true' }
        { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: insights.properties.ConnectionString }
        { name: 'AZURE_OPENAI_ENDPOINT', value: openai.properties.endpoint }
        { name: 'AZURE_OPENAI_DEPLOYMENT', value: deployment.name }
        { name: 'ACS_CONNECTION_STRING', value: comms.listKeys().primaryConnectionString }
        { name: 'EMAIL_SENDER', value: 'DoNotReply@${emailDomain.properties.mailFromSenderDomain}' }
        { name: 'EMAIL_TO', value: emailTo }
        { name: 'LOCAL_LOCATIONS', value: localLocations }
        { name: 'MIN_SCORE', value: string(minScore) }
        { name: 'JOB_PREFERENCES', value: jobPreferences }
        { name: 'ADZUNA_APP_ID', value: adzunaAppId }
        { name: 'ADZUNA_APP_KEY', value: adzunaAppKey }
      ]
    }
  }
}

// Cognitive Services OpenAI User
var openAiUserRole = '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
resource openAiRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(openai.id, func.id, openAiUserRole)
  scope: openai
  properties: {
    principalId: func.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', openAiUserRole)
  }
}

output functionAppName string = func.name
output storageAccountName string = storage.name
output emailSender string = 'DoNotReply@${emailDomain.properties.mailFromSenderDomain}'
