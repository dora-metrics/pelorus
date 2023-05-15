#!/usr/bin/env bash
#
# Copyright Red Hat
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
#

OPERATOR_PROJECT_NAME=pelorus-operator
OPERATOR_ORG_NAME=pelorus
OPERATOR_PROJECT_DOMAIN=pelorus.dora-metrics.io

# Get the full absolute path to the script. Needed while calling the script
# via various partial paths or sourcing the file from shell
# BASH_SOURCE[0] is safer then $0 when sourcing.
# We enter the dirname of the invoked script and then get the current
# path of the script using pwd
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

DEFAULT_PELORUS_CHARTS_SUBDIR="../charts/pelorus"
DEFAULT_PELORUS_CHARTS_DIR="${SCRIPT_DIR}/${DEFAULT_PELORUS_CHARTS_SUBDIR}/"
DEFAULT_PELORUS_OPERATOR_DIR="${SCRIPT_DIR}/../pelorus-operator/"
DEFAULT_PELORUS_OPERATOR_PATCHES_DIR="${SCRIPT_DIR}/pelorus-operator-patches/"

TRUE=1

function print_help() {
    printf "\nUsage: %s [OPTION]\n\n" "$0"
    printf "\tStartup:\n"
    printf "\t  -h\tprint this help\n"
    printf "\n\tOptions:\n"
    printf "\t  -s\tpath to source pelorus helm charts folder, default: %s\n" "${DEFAULT_PELORUS_CHARTS_DIR}"
    printf "\t  -d\tpath to destination folder, default: %s\n" "${DEFAULT_PELORUS_OPERATOR_DIR}"
    printf "\t  -p\tpath to DIR with operator patches to be applied, default: %s\n" "${DEFAULT_PELORUS_OPERATOR_PATCHES_DIR}"
    printf "\t  -o\tQuay user/org name, default to pelorus, which is the production storage.\n"
    printf "\t  -f\tforce, removes destination folder that must be named pelorus-operator before proceeding\n"
    printf "\t  -x\tbump X part of the version (Y and Z are set to 0, so X.0.0)\n"
    printf "\t  -y\tbump Y version (Z will start at 0, so X.Y.0)\n"
    printf "\t  -z\tbump Z version (Z in the X.Y.Z)\n"
    printf "\t  -n\tbump RC number (N in X.Y.Z-rc.N)\n"
    exit 0
}

OPTIONS_COUNTER=0

### Options
OPTIND=1
while getopts "fs:d:p:h?xyzno:" option; do
    case "$option" in
    h|\?) print_help;;
    s)    source_dir=$OPTARG;;
    d)    destination_dir=$OPTARG;;
    p)    patches_dir=$OPTARG;;
    o)    quay_user=$OPTARG;;
    f)    force="$TRUE";;
    x)    x_ver="$TRUE"; OPTIONS_COUNTER=$((OPTIONS_COUNTER + 1));;
    y)    y_ver="$TRUE"; OPTIONS_COUNTER=$((OPTIONS_COUNTER + 1));;
    z)    z_ver="$TRUE"; OPTIONS_COUNTER=$((OPTIONS_COUNTER + 1));;
    n)    rc_ver="$TRUE"; OPTIONS_COUNTER=$((OPTIONS_COUNTER + 1));;
    esac
done

if [ $OPTIONS_COUNTER -eq 0 ]; then
    printf "\nERROR: No options were provided.\n"
    exit 1
elif [ $OPTIONS_COUNTER -gt 1 ]; then
    printf "\nERROR: Provide only one option.\n"
    exit 1
fi

# Check preconditions
if ! oc auth can-i '*' '*' --all-namespaces &> /dev/null; then
    echo "You must be logged in to a OpenShift cluster as a user with cluster-admin permissions to run this script."
    echo "This avoids RBAC problems. More info: https://sdk.operatorframework.io/docs/building-operators/helm/tutorial/#prerequisites"
    exit 1
fi
if ! oc get crd grafanas.integreatly.org &> /dev/null; then
    echo "Grafana CRD not found."
    exit 1
fi
if ! oc get crd prometheuses.monitoring.coreos.com &> /dev/null; then
    echo "Prometheus CRD not found."
    exit 1
fi

if [ -z ${source_dir+x} ]; then
    source_dir="${DEFAULT_PELORUS_CHARTS_DIR}"
fi
if [ -z ${destination_dir+x} ]; then
    destination_dir="${DEFAULT_PELORUS_OPERATOR_DIR}"
fi
if [ -z ${patches_dir+x} ]; then
    patches_dir="${DEFAULT_PELORUS_OPERATOR_PATCHES_DIR}"
fi
if [ -n "${quay_user}" ]; then
    OPERATOR_ORG_NAME="${quay_user}"
fi

echo "INFO: Source directory: ${source_dir}"
echo "INFO: Destination directory: ${destination_dir}"
echo "INFO: Patches directory: ${patches_dir}"

if ! [ -x "$(command -v "operator-sdk")" ]; then
    echo "ERROR: operator-sdk CLI not found. Please activate Pelorus venv!"
    exit 2
else
    echo "INFO: $(operator-sdk version)"
fi

# Check if source directory exists
if [ ! -d "${source_dir}" ]; then
	echo "ERROR: Source directory ${source_dir} does not exists."
    exit 2
fi

# Check if the destination directory path ends with /pelorus-operator/
if [[ "${destination_dir}" == *"/pelorus-operator/" && $force ]]; then
    echo "INFO: Removing operator directory: ${destination_dir}"
    rm -rf "${destination_dir}"
    echo "INFO: Creating new operator directory: ${destination_dir}"
    mkdir "${destination_dir}"
fi

# Check if destination directory is empty and exists
if [ -d "${destination_dir}" ]; then
	if [ "$(ls -A "${destination_dir}")" ]; then
        echo "ERROR: Destination directory ${destination_dir} is not empty, can not continue."
        exit 2
	fi
else
	echo "ERROR: Destination directory ${destination_dir} do not exists, please create one and re-run script."
    exit 2
fi

pushd "${destination_dir}" || exit 2
    echo "INFO: Creating operator init files"
    operator-sdk init --plugins=helm --domain "${OPERATOR_PROJECT_DOMAIN}" --project-name "${OPERATOR_PROJECT_NAME}" || exit 2
    echo "INFO: Creating api"
    mkdir -p helm-charts/pelorus/charts
    cp -r "${source_dir}charts/exporters" helm-charts/pelorus/charts
    operator-sdk create api --helm-chart="${source_dir}" || exit 2
    rm helm-charts/pelorus/charts/*.tgz

    # Correct operator version, to be latest +1
    OPERATOR_VERSIONS=$(curl -H "Authorization: Bearer XYZ" -X GET "https://quay.io/api/v1/repository/${OPERATOR_ORG_NAME}/${OPERATOR_PROJECT_NAME}/tag/" 2> /dev/null | jq ".tags[] | select(.end_ts == null) | .name" | sed -e 's|\"||g' | grep -E '^[0-9]+\.[0-9]+\.[0-9]+$' -o | sort -t. -nrk1,1 -nrk2,2 -nrk3,3)
    OPERATOR_VERSION=$(echo "$OPERATOR_VERSIONS" | head -1 )
    echo "INFO: Current operator version: ${OPERATOR_VERSION}"

    OPERATOR_MAKEFILE_IN_MASTER="$(curl https://raw.githubusercontent.com/dora-metrics/pelorus/master/pelorus-operator/Makefile 2> /dev/null)"
    OPERATOR_VERSION_IN_MASTER=$(echo "$OPERATOR_MAKEFILE_IN_MASTER" | grep "VERSION ?= " | cut -c 12-)
    # shellcheck disable=SC2207
    CURRENT_VERSION_ARRAY=( $(echo "$OPERATOR_VERSION_IN_MASTER" | sed "s/-rc//g" | tr ' . '  '  ') )
    V_X_VER=${CURRENT_VERSION_ARRAY[0]}
    V_Y_VER=${CURRENT_VERSION_ARRAY[1]}
    V_Z_VER=${CURRENT_VERSION_ARRAY[2]}
    V_RC_VER=${CURRENT_VERSION_ARRAY[3]}

    RC_SUFFIX=""
    if [[ $x_ver ]]; then
        V_X_VER=$(( V_X_VER +  1 ))
        V_Y_VER="0"
        V_Z_VER="0"
    elif [[ $y_ver ]]; then
        V_Y_VER=$(( V_Y_VER +  1 ))
        V_Z_VER="0"
    elif [[ $z_ver ]]; then
        # Only bump the Z version if -rc.N was missing
        # Otherwise remove the -rc.N as it's our next release
        if [[ -z "${V_RC_VER}" ]]; then
            V_Z_VER=$(( V_Z_VER +  1 ))
        fi
    elif [[ $rc_ver ]]; then
        if [[ -z "${V_RC_VER}" ]]; then
            # Start from the first RC number of the next Z release
            V_RC_VER=1
        else
            V_RC_VER=$(( V_RC_VER +  1 ))
        fi
        RC_SUFFIX="-rc.${V_RC_VER}"
    fi
    NEW_OPERATOR_VERSION="$V_X_VER.$V_Y_VER.$V_Z_VER$RC_SUFFIX"

    sed -i "s/VERSION ?= 0.0.1/VERSION ?= ${NEW_OPERATOR_VERSION}/g" Makefile || exit 2

    # Correct IMAGE_TAG_BASE
    IMAGE_TAG_BASE="quay.io/${OPERATOR_ORG_NAME}/${OPERATOR_PROJECT_NAME}"
    echo "INFO: Setting IMAGE_TAG_BASE to ${IMAGE_TAG_BASE}"
    sed -i "s#IMAGE_TAG_BASE ?=.*#IMAGE_TAG_BASE ?= ${IMAGE_TAG_BASE}#g" Makefile || exit 2

    # Generate kustomize files. This is similar to the first command from
    # Make bundle, except we do want to have non-interactive version
    echo "INFO: Generating kustomize manifests files"
    operator-sdk generate kustomize manifests -q --interactive=false
popd || exit 2

# Check if patches directory exists
if [ ! -d "${patches_dir}" ]; then
    echo "WARNING: Patches directory ${patches_dir} do not exists, patches will not be applied."
elif [ "$(ls -A "${patches_dir}"/*.diff 2>/dev/null)" ]; then
    echo "INFO: Found patches in ${patches_dir}."
    for patch_file in "${patches_dir}"/*.diff; do
        echo "INFO: Applying patch ${patch_file}"
        patch -d "${destination_dir}" -p0 < "${patch_file}" || exit 2
    done
fi

pushd "${destination_dir}" || exit 2

    # Set proper value for the 'metadata.annotations.containerImage'
    # We first patch the config/manifests/bases/pelorus-operator.clusterserviceversion.yaml
    # with "containerImage: placeholder", because we don't know which ORG the image will be
    # pushed to and in this step we set correct containerImage metadata.
    OPERATOR_RESULTING_IMG="quay.io/${OPERATOR_ORG_NAME}/${OPERATOR_PROJECT_NAME}:${NEW_OPERATOR_VERSION}"
    echo "INFO: Operator Image containerImage: ${OPERATOR_RESULTING_IMG}"
    sed -i "s#^    containerImage: placeholder#    containerImage: ${OPERATOR_RESULTING_IMG}#g" config/manifests/bases/pelorus-operator.clusterserviceversion.yaml || exit 2

    echo "INFO: Executing make bundle"
    make bundle
popd || exit 2

# Check if patches directory exists
# The bundle patches can be applied after generating bundle
if [ ! -d "${patches_dir}/bundle-patches" ]; then
	echo "WARNING: Bundle patches directory ${patches_dir}/bundle-patches do not exists, bundle patches will not be applied."
elif [ "$(ls -A "${patches_dir}/bundle-patches"/*.diff 2>/dev/null)" ]; then
        echo "INFO: Found bundle patches in ${patches_dir}/bundle-patches."
        for patch_file in "${patches_dir}"/bundle-patches/*.diff; do
            echo "INFO: Applying bundle patch ${patch_file}"
            patch -d "${destination_dir}" -p0 < "${patch_file}" || exit 2
        done
fi

echo "INFO: Adding replaces and skips entries to ${source_dir}${destination_dir}/bundle/manifests/charts.pelorus.dora-metrics.io_pelorus.yaml"
set -e
# shellcheck disable=SC2086 # We need to expand $OPERATOR_VERSIONS
$SCRIPT_DIR/specify_operator_update.py $NEW_OPERATOR_VERSION $destination_dir $OPERATOR_VERSIONS

echo "INFO: Current operator version: ${OPERATOR_VERSION}"
echo "INFO: New operator version: ${NEW_OPERATOR_VERSION}"

echo "INFO: Operator crated and available at: ${destination_dir}"
echo "To build and push to the quay use from the operator folder:"
echo "  # podman login -u="migtools+pelorus" -p=\"\$QUAY_TOKEN\" quay.io"
echo "  # make podman-build"
echo "  # make podman-push"
echo "  # make bundle-build"
echo "  # make bundle-push"
echo "  # # Log in to your cluster or export KUBECONFIG"
echo "  # # Deploy bundle, e.g. version v${NEW_OPERATOR_VERSION} in the pelorus namespace"
echo "  # operator-sdk run bundle quay.io/${OPERATOR_ORG_NAME}/pelorus-operator-bundle:v${NEW_OPERATOR_VERSION} --namespace pelorus"
echo "  # # Create pelorus instance from example in the pelorus namespace"
echo "  # oc apply -f pelorus-operator/config/samples/charts_v1alpha1_pelorus.yaml -n pelorus"
