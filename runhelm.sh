#!/bin/bash

export PROMETHEUS_HTPASSWD_AUTH=$(oc get secret prometheus-k8s-htpasswd -n openshift-monitoring -o jsonpath='{.data.auth}')
export GRAFANA_DATASOURCE_PASSWORD=$(oc get secret grafana-datasources -n openshift-monitoring -o jsonpath='{.data.prometheus\.yaml}' | base64 -d | jq .datasources[0].basicAuthPassword)
export PROMETHEUS_HTPASSWD_AUTH=$(oc get secret prometheus-k8s-htpasswd -n openshift-monitoring -o jsonpath='{.data.auth}')

NOOBA_INSTALLED=$(oc projects | grep -c nooba )
echo "Nooba installed: $NOOBA_INSTALLED"
if [ $NOOBA_INSTALLED -ne "1" ]; then
    oc new-project noobaa
    noobaa install | tee noobaa_install_details
    export AWS_ACCESS_KEY_ID=$(cat noobaa_install_details | grep AWS_ACCESS_KEY_ID | sed 's/^.*: //')
    export AWS_SECRET_ACCESS_KEY=$(cat noobaa_install_details | grep AWS_SECRET_ACCESS_KEY | sed 's/^.*: //')
    export ENDPOINT=$(oc get routes -n noobaa | grep s3 | awk '{print $2}')
    aws --endpoint https://$ENDPOINT --no-verify-ssl s3 mb s3://thanos
    oc project default
fi

export NOOBAA_AWS_ACCESS_KEY=$(cat noobaa_install_details | grep AWS_ACCESS_KEY_ID | sed 's/^.*: //')
export NOOBAA_AWS_SECRET_ACCESS_KEY=$(cat noobaa_install_details | grep AWS_SECRET_ACCESS_KEY | sed 's/^.*: //')

helm template \
    --namespace pelorus \
    pelorus \
    --set openshift_prometheus_htpasswd_auth=$PROMETHEUS_HTPASSWD_AUTH \
    --set internal_prometheus_basic_auth_pass=$GRAFANA_DATASOURCE_PASSWORD \
    --set noobaa_aws_access_key=$NOOBAA_AWS_ACCESS_KEY \
    --set noobaa_aws_secret_access_key=$NOOBAA_AWS_SECRET_ACCESS_KEY \
    ./charts/deploy/ | oc apply -f - -n pelorus
