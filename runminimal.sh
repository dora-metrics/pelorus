#!/bin/bash

namespace=pelorus

PELORUS_ARGS=""

while getopts ":n:" opt; do
  case ${opt} in
    n )
      namespace=$OPTARG
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


set -o pipefail
helm template \
    --namespace ${namespace} \
    pelorus \
    ./charts/minimal/ | oc apply -f - -n ${namespace}

HELM_STATUS=$?

if [ $HELM_STATUS -ne 0 ]; then
    echo "Error in template processing and application!"
fi

exit $HELM_STATUS
