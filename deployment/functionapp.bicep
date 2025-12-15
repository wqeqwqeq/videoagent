// ================================================================
// VideoAgent Function App Infrastructure
// ================================================================
// Creates:
//   - Function App (Python 3.12, Linux, attached to existing plan)
//   - Storage Container (in existing storage account)
//
// Prerequisites (existing resources):
//   - Resource Group
//   - App Service Plan
//   - Storage Account
//   - Log Analytics Workspace
//   - Application Insights
// ================================================================

// ================================================================
// Parameters
// ================================================================

@description('Resource naming prefix (e.g., videoagent)')
param resourcePrefix string

@description('Azure region for resources')
param location string = resourceGroup().location

@description('Existing App Service Plan name')
param appServicePlanName string

@description('Existing Storage Account name')
param storageAccountName string

@description('Existing Log Analytics Workspace name')
param logAnalyticsWorkspaceName string

@description('Existing Application Insights name')
param appInsightsName string

@description('Storage container name for output files')
param storageContainerName string = 'videoagent-output'

@description('CRON schedule for orchestrator timer (e.g., 0 0 6 * * *)')
param orchestratorSchedule string = '0 0 6 * * *'

@description('CRON schedule for video generator timer (e.g., 0 0 7 * * *)')
param videoSchedule string = '0 0 7 * * *'

// ================================================================
// Variables
// ================================================================

var functionAppName = '${resourcePrefix}-func'

// ================================================================
// Existing Resources
// ================================================================

resource existingStorageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' existing = {
  name: storageAccountName
}

resource existingAppInsights 'Microsoft.Insights/components@2020-02-02' existing = {
  name: appInsightsName
}

resource existingAppServicePlan 'Microsoft.Web/serverfarms@2023-01-01' existing = {
  name: appServicePlanName
}

resource existingLogAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2022-10-01' existing = {
  name: logAnalyticsWorkspaceName
}

// ================================================================
// Storage Container
// ================================================================

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-01-01' existing = {
  parent: existingStorageAccount
  name: 'default'
}

resource videoAgentContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  parent: blobService
  name: storageContainerName
  properties: {
    publicAccess: 'None'
  }
}

// ================================================================
// Function App
// ================================================================

resource functionApp 'Microsoft.Web/sites@2023-01-01' = {
  name: functionAppName
  location: location
  kind: 'functionapp,linux'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: existingAppServicePlan.id
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'PYTHON|3.12'
      pythonVersion: '3.12'
      appSettings: [
        // Azure Functions Runtime Settings
        {
          name: 'AzureWebJobsStorage'
          value: 'DefaultEndpointsProtocol=https;AccountName=${storageAccountName};EndpointSuffix=${environment().suffixes.storage};AccountKey=${existingStorageAccount.listKeys().keys[0].value}'
        }
        {
          name: 'WEBSITE_CONTENTAZUREFILECONNECTIONSTRING'
          value: 'DefaultEndpointsProtocol=https;AccountName=${storageAccountName};EndpointSuffix=${environment().suffixes.storage};AccountKey=${existingStorageAccount.listKeys().keys[0].value}'
        }
        {
          name: 'WEBSITE_CONTENTSHARE'
          value: toLower(functionAppName)
        }
        {
          name: 'FUNCTIONS_EXTENSION_VERSION'
          value: '~4'
        }
        {
          name: 'FUNCTIONS_WORKER_RUNTIME'
          value: 'python'
        }
        // Remote Build Settings
        {
          name: 'SCM_DO_BUILD_DURING_DEPLOYMENT'
          value: 'true'
        }
        {
          name: 'ENABLE_ORYX_BUILD'
          value: 'true'
        }
        // Application Insights
        {
          name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
          value: existingAppInsights.properties.ConnectionString
        }
        // VideoAgent Storage Settings
        {
          name: 'STORAGE_MODE'
          value: 'blob'
        }
        {
          name: 'STORAGE_ACCOUNT_NAME'
          value: storageAccountName
        }
        {
          name: 'STORAGE_CONTAINER'
          value: storageContainerName
        }
        // Timer Schedules
        {
          name: 'ORCHESTRATOR_SCHEDULE'
          value: orchestratorSchedule
        }
        {
          name: 'VIDEO_SCHEDULE'
          value: videoSchedule
        }
      ]
      ftpsState: 'Disabled'
      minTlsVersion: '1.2'
    }
  }
}

// ================================================================
// Diagnostic Settings (link to existing Log Analytics)
// ================================================================

resource functionAppDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: '${functionAppName}-diagnostics'
  scope: functionApp
  properties: {
    workspaceId: existingLogAnalyticsWorkspace.id
    logs: [
      {
        category: 'FunctionAppLogs'
        enabled: true
      }
    ]
    metrics: [
      {
        category: 'AllMetrics'
        enabled: true
      }
    ]
  }
}

// ================================================================
// Role Assignment - Storage Blob Data Contributor
// ================================================================

// Storage Blob Data Contributor role definition ID
var storageBlobDataContributorRoleId = 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'

resource storageRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(existingStorageAccount.id, functionApp.id, storageBlobDataContributorRoleId)
  scope: videoAgentContainer
  properties: {
    principalId: functionApp.identity.principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageBlobDataContributorRoleId)
    principalType: 'ServicePrincipal'
  }
}

// ================================================================
// Outputs
// ================================================================

output functionAppName string = functionApp.name
output functionAppUrl string = 'https://${functionApp.properties.defaultHostName}'
output functionAppPrincipalId string = functionApp.identity.principalId
output storageContainerName string = videoAgentContainer.name
