param logAnalyticsWorkspaceName string = 'law-easytelemetry'
param applicationInsightsName string = 'appi-easytelemetry'
param location string = resourceGroup().location
param dailyCapInGB int = 1
param retentionInDays int = 30

resource law 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: logAnalyticsWorkspaceName
  location: location
  properties: {    
    retentionInDays: retentionInDays
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
    workspaceCapping: {
      dailyQuotaGb: dailyCapInGB
    }
  }
}

resource appi 'Microsoft.Insights/components@2020-02-02' = {
  name: applicationInsightsName
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: law.id
    RetentionInDays: retentionInDays
  }
}

output logAnalyticsWorkspaceId string = law.id
output appInsightsId string = appi.id
output appInsightsConnectionString string = appi.properties.ConnectionString

