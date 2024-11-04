#!/usr/bin/env bash

subscription_id=''
deployment_suffix='1'
rg=''
delete=''
location='germanywestcentral'

while [[ "$#" -gt 0 ]]; do
    case $1 in
        -s|--subscription) subscription_id="$2"; shift;;
        -i|--deployment-suffix) deployment_suffix="$2"; shift;;
        -g|--resource-group) rg="$2"; shift ;;
        -d|--delete) delete='true' ;;
        *) echo "Unknown parameter passed: $1"; exit 1 ;;
    esac
    shift
done

if [ -z "$rg" ]; then
    rg="rg-easytelemetry-$deployment_suffix"
fi

if [ "$delete" == 'true' ]; then
    az group delete --subscription "$subscription_id" -n "$rg" --no-wait --yes
    exit 0
fi

az config set extension.use_dynamic_install=yes_without_prompt --only-show-errors
az group create --subscription "$subscription_id" -n "$rg" --location "$location" --only-show-errors

az deployment group create --subscription "$subscription_id" -g "$rg" -f integration_tests.bicep \
  -n "deploy-confeasy-$deployment_suffix" \
  --query "properties.outputs.appcConnStr.value" -o tsv
