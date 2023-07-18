# Integration Tests

1) Create Application Insights resource in your Azure Portal
and obtain connection string for the client.

2) Set up environment property `TESTS_APPLICATION_INSIGHTS_CONNECTION_STRING`
or `APPLICATION_INSIGHTS_CONNECTION_STRING`.

3) Optionally you can also set up environment properties (best practice):
- `APP_VERSION` or `TESTS_APP_VERSION` (semantic version, such as '1.1.0.6')
- `ENVIRONMENT` or `TESTS_ENVIRONMENT` (dev | test | stage | prod)
- `COMPUTERNAME` or `TESTS_COMPUTERNAME`

If you do not set up these variables, there are sensible defaults, but you might want better control
of what metadata are passed with each log or metric to ingestion endpoint.

## Creating Application Insights using az CLI

```shell
az login
az account set --subscription SUBSCRIPTION

# Create Log Analytics Workspace with minimal retention time and daily quota.
az monitor log-analytics workspace create -n WSNAME -l LOCATION -g RESGRP --retention-time 30 --quota 2

# Create Application Insights.
az monitor app-insights component create -a NAME -l LOCATION -g RESGRP --workspace WSNAME

# Set daily cap to 2GB, it must be same or smaller than workspace quota.
# Inside workspace you can create more than one Application Insights resource
az monitor app-insights component billing update -a NAME -g RESGRP --cap 2
```

- **SUBSCRIPTION** Azure subscription name
- **RESGRP** resource group name, for example `tests-rg`
- **WSNAME** Log Analytics Workspace resource name, such as `tests-law`
- **NAME** Application Insights resource name, for example `tests-ai`
- **LOCATION** Azure datacenter location, such as `westeurope`,<br />
  to see all available: `az account list-locations -o table`

