#!/bin/bash

namespace=pelorus
skip_auth=false

PELORUS_ARGS=""

while getopts ":n:v:s:k" opt; do
  case ${opt} in
    n )
      namespace=$OPTARG
      ;;
    v )
      EXTRA_VALUES="${EXTRA_VALUES} --values ${OPTARG}"
      ;;
    s )
      EXTRA_VALUES="${EXTRA_VALUES} --set ${OPTARG}"
      ;;
    k )
      skip_auth=true
      ;;
    \? )
      echo "Invalid option: $OPTARG" 1>&2
      exit 1
      ;;
    : )
      echo "Invalid option: $OPTARG requires an argument" 1>&2
      exit 1
      ;;
  esac
done
shift $((OPTIND -1))

if [ "$skip_auth" = false ]; then
  echo  "skip_auth is $skip_auth"
  exit 1

  export GRAFANA_DATASOURCE_PASSWORD=$(oc get secret grafana-datasources -n openshift-monitoring -o jsonpath='{.data.prometheus\.yaml}' | base64 --decode | jq .datasources[0].basicAuthPassword | sed 's/"//g' )

  if [ -z $GRAFANA_DATASOURCE_PASSWORD ]; then
      echo "Could not find the Grafana datasource password in the openshift-monitoring namespace!"
      exit 1
  fi

  PELORUS_ARGS="--set openshift_prometheus_htpasswd_auth=${PROMETHEUS_HTPASSWD_AUTH}"

  export PROMETHEUS_HTPASSWD_AUTH=$(oc get secret prometheus-k8s-htpasswd -n openshift-monitoring -o jsonpath='{.data.auth}')
  if [ -z $PROMETHEUS_HTPASSWD_AUTH ]; then
      echo "Could not find the prometheus htpasswd file secret in the openshift-monitoring namespace!"
      exit 1
  fi

  PELORUS_ARGS="${PELORUS_ARGS} --set openshift_prometheus_basic_auth_pass=${GRAFANA_DATASOURCE_PASSWORD}"
fi

set -o pipefail
helm template \
    --namespace ${namespace} \
    pelorus ${PELORUS_ARGS} \
    $EXTRA_VALUES \
    ./charts/deploy/ | oc apply -f - -n ${namespace}

HELM_STATUS=$?

if [ $HELM_STATUS -ne 0 ]; then
    echo "Error in template processing and application!"
fi

exit $HELM_STATUS
