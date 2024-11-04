# Integration Tests

1) Create Application Insights resource in your Azure Portal
and obtain connection string for the client.

2) Set up environment property `TESTS_APPLICATION_INSIGHTS_CONNECTION_STRING`
or `APPLICATION_INSIGHTS_CONNECTION_STRING`.

3) Optionally you can also set up environment properties (best practice):
- `APP_VERSION` or `TESTS_APP_VERSION` (semantic version, such as '1.1.0')
- `ENVIRONMENT` or `TESTS_ENVIRONMENT` (dev | test | stage | prod)
- `COMPUTERNAME` or `TESTS_COMPUTERNAME`

If you do not set up these variables, there are sensible defaults, but you might want better control
of what metadata are passed with each log or metric to ingestion endpoint.

## Creating Application Insights using az CLI

```shell
az login

az deployment group create --subscription "{subscription_id}" -g "{resource_group}" -f integration_tests.bicep \
  -n "deploy-easytelemetry-1" \
  --query "properties.outputs.appInsightsConnectionString.value" -o tsv
```

