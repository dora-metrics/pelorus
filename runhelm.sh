#!/bin/bash

namespace=pelorus

while getopts ":n:v:s:" opt; do
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

export GRAFANA_DATASOURCE_PASSWORD=$(oc get secret grafana-datasources -n openshift-monitoring -o jsonpath='{.data.prometheus\.yaml}' | base64 --decode | jq .datasources[0].basicAuthPassword | sed 's/"//g' )

if [ -z $GRAFANA_DATASOURCE_PASSWORD ]; then
    echo "Could not find the Grafana datasource password in the openshift-monitoring namespace!"
    exit 1
fi

export PROMETHEUS_HTPASSWD_AUTH=$(oc get secret prometheus-k8s-htpasswd -n openshift-monitoring -o jsonpath='{.data.auth}')
if [ -z $PROMETHEUS_HTPASSWD_AUTH ]; then
    echo "Could not find the prometheus htpasswd file secret in the openshift-monitoring namespace!"
    exit 1
fi

set -o pipefail
helm template \
    --namespace ${namespace} \
    pelorus \
    --set openshift_prometheus_htpasswd_auth=$PROMETHEUS_HTPASSWD_AUTH \
    --set openshift_prometheus_basic_auth_pass=$GRAFANA_DATASOURCE_PASSWORD \
    $EXTRA_VALUES \
    ./charts/deploy/ | oc apply -f - -n ${namespace}

HELM_STATUS=$?

if [ $HELM_STATUS -ne 0 ]; then
    echo "Error in template processing and application!"
fi

exit $HELM_STATUS
