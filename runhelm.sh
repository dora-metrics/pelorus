#!/bin/bash

export GRAFANA_DATASOURCE_PASSWORD=$(oc get secret grafana-datasources -n openshift-monitoring -o jsonpath='{.data.prometheus\.yaml}' | base64 -d | jq .datasources[0].basicAuthPassword | sed 's/"//g' )
export PROMETHEUS_HTPASSWD_AUTH=$(oc get secret prometheus-k8s-htpasswd -n openshift-monitoring -o jsonpath='{.data.auth}')

#Allow passing a values file to override helm variables.
if [ "$1" == "--values" ] && [ "x" != "x$2" ]; then
    EXTRA_VALUES="$1 $2"
fi

helm template \
    --namespace pelorus \
    pelorus \
    --set openshift_prometheus_htpasswd_auth=$PROMETHEUS_HTPASSWD_AUTH \
    --set openshift_prometheus_basic_auth_pass=$GRAFANA_DATASOURCE_PASSWORD \
    $EXTRA_VALUES \
    ./charts/deploy/  | tee | oc apply -f - -n pelorus
