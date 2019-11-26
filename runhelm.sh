#!/bin/bash

export PROMETHEUS_HTPASSWD_AUTH=$(oc get secret prometheus-k8s-htpasswd -n openshift-monitoring -o jsonpath='{.data.auth}')
export GRAFANA_DATASOURCE_PASSWORD=$(oc get secret grafana-datasources -n openshift-monitoring -o jsonpath='{.data.prometheus\.yaml}' | base64 -d | jq .datasources[0].basicAuthPassword)
export PROMETHEUS_HTPASSWD_AUTH=$(oc get secret prometheus-k8s-htpasswd -n openshift-monitoring -o jsonpath='{.data.auth}')

helm template \
    --namespace pelorus \
    pelorus \
    --set openshift_prometheus_htpasswd_auth=$PROMETHEUS_HTPASSWD_AUTH \
    --set internal_prometheus_basic_auth_pass=$GRAFANA_DATASOURCE_PASSWORD \
    ./charts/deploy/ | oc apply -f - -n pelorus
