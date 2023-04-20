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

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
# Match the .venv created by the Makefile
DEFAULT_VENV="${SCRIPT_DIR}/../.venv"
TMP_DIR_PREFIX="pelorus_tmp_"
PELORUS_NAMESPACE="pelorus"
# Used in CI
PROW_SECRETS_DIR="/var/run/konveyor/pelorus/pelorus-github/"
PROW_S3_SECRETS_DIR="/var/run/konveyor/pelorus/pelorus-s3amazon/"

# Binary build script
BINARY_BUILD_SCRIPT="${SCRIPT_DIR}/e2e-tests-templates/build_binary_app.sh"

# Needs to match the SECRET_TOKEN from the Pelorus configuration files
WEBHOOK_SECRET_TOKEN="MySecretToken"
WEBHOOK_EXPORTER_WITH_SECRET_NAME="webhook-secret-exporter"
WEBHOOK_EXPORTER_NAME="webhook-exporter"

# Used to download required files prior to running the job
# Arguments:
#    $1 - URL from which download the file
#    $2 - File name of the output file
#    $3 - (Optional) - destination directory, defaults to SCRIPT_DIR
function download_file_from_url() {
    local url=$1
    local file_name=$2
    local dest_folder="${3:-$SCRIPT_DIR}" # Use ./ as default dest_folder

    pushd "${dest_folder}" || exit
      echo "Downloading file: ${url}"
      echo "To: ${dest_folder}/${file_name}"
      if curl --fail-with-body --help >/dev/null 2>&1; then
          curl --fail-with-body -Lo "${file_name}" "${url}" || exit
      elif type curl; then
          curl -Lo "${file_name}" "${url}" || exit
      else
          wget -O "${file_name}" "${url}" || exit
      fi
    popd || exit
}

# Function to safely remove temporary files and temporary download dir
# Argument is optional exit value to propagate it after cleanup
function cleanup_and_exit() {
    echo "===== Cleaning up and exiting ====="
    local exit_val=$1
    if [ -z "${DWN_DIR}" ]; then
        echo "cleanup_and_exit(): Temp download dir not provided !" >&2
    else
      # Ensure dir exists and starts with prefix
      if [ -d "${DWN_DIR}" ]; then
          PELORUS_TMP_DIR=$(basename "${DWN_DIR}")
          if [[ "${PELORUS_TMP_DIR}" =~ "${TMP_DIR_PREFIX}"* ]]; then
              echo "Cleaning up temporary files"
              rm -rf "${DWN_DIR}"
          fi
      fi
    fi
    # Show logs from all pods.
    echo "===== Pod Logs ====="
    for pod in $(oc get pods -n "${PELORUS_NAMESPACE}" -o name); do
        echo "----- Logs from ${pod} -----"
        oc logs -n "${PELORUS_NAMESPACE}" --all-containers "${pod}"
    done

    # Cleanup binary builds
    for binary_build_ns in "${BINARY_BUILDS_NAMESPACES[@]}"; do
        "${BINARY_BUILD_SCRIPT}" -c -n "${binary_build_ns}"
    done

    # Propagate exit value if was provided
    [ -n "${exit_val}" ] && echo "Exit code: ${exit_val}" && exit "$exit_val"
    exit 0
}

function retry() {
    local timeout="$1"; shift
    local sleep_time="$1"; shift
    local cmd="$*"
    # Let's print what is happening in the subshell
    set -x
    timeout "$timeout" bash -c "until ${cmd}; do sleep ${sleep_time}; done" || exit 2
    set +x
}

function print_help() {
    printf "\nUsage: %s [OPTION]... -d [DIR]\n\n" "$0"
    printf "\tStartup:\n"
    printf "\t  -h\tprint this help\n"
    printf "\n\tOptions:\n"
    printf "\t  -o\tgithub organization of the mig-demo-apps. By default, konveyor\n"
    printf "\t  -b\tbranch of the mig-demo-apps. By default, master\n"
    printf "\t  -f\tvalues filename of the mig-demo-apps. By default, values.yaml\n"
    printf "\t  -d\tpath to Python virtual environment DIR. By default, the project's one\n"
    printf "\t  -s\t(USED ONLY IN PROW CI) path to DIR with secrets files. For local runs, run 'export SECRET_NAME=VALUE'\n"
    printf "\t  -t\tenable Thanos (long term persistent storage) tests with s3 bucket\n"
    printf "\t  -c\tpath to DIR with secrets files for s3 bucket\n"
    printf "\t  -a\tenable all exporter tests \n"
    printf "\t  -e\tenable selected exporter tests (comma separated). Examples:\n"
    printf "\t\t  -e failure\n"
    printf "\t\t  -e gitlab_committime,jira_committime\n"
    printf "\t\tavailable options:\n"
    printf "\t\t  failure - GitHub issue tracker - REQUIRES 'TOKEN=YOUR_GITHUB_TOKEN' SECRET\n"
    printf "\t\t  gitlab_committime - GitLab git provider - REQUIRES 'GITLAB_API_TOKEN=YOUR_GITLAB_TOKEN' SECRET\n"
    printf "\t\t  gitea_committime - Gitea git provider - REQUIRES 'GITEA_API_TOKEN=YOUR_GITEA_TOKEN' SECRET\n"
    printf "\t\t  bitbucket_committime - Bitbucket git provider - REQUIRES 'BITBUCKET_API_USER=YOUR_BITBUCKET_USER' AND 'BITBUCKET_API_TOKEN=YOUR_BITBUCKET_TOKEN' SECRETS\n"
    printf "\t\t  azure-devops-committime - Azure devops git provider - REQUIRES 'AZURE_DEVOPS_TOKEN=YOUR_AZURE_DEVOPS_TOKEN' SECRET\n"
    printf "\t\t  jira_committime - Jira issue tracker - REQUIRES 'JIRA_USER=YOUR_JIRA_USER' AND 'JIRA_TOKEN=YOUR_JIRA_TOKEN' SECRETS\n"
    printf "\t\t  jira_custom_committime - Jira issue tracker - REQUIRES 'JIRA_USER=YOUR_JIRA_USER' AND 'JIRA_TOKEN=YOUR_JIRA_TOKEN' SECRETS\n"
    printf "\t\t  pagerduty_failure - PagerDuty issue tracker - REQUIRES 'PAGER_DUTY_TOKEN=YOUR_PAGER_DUTY_TOKEN' SECRET\n"
    printf "\t\t  webhook - Webhook exporter\n"
    printf "\t\t  webhook_with_secret - Webhook exporter with '%s' SECRET_TOKEN\n" "${WEBHOOK_SECRET_TOKEN}"

    exit 0
}

# We use exported functions instead of aliases, so they are available
# in subshell. This is required for timeout.
set -a
# shellcheck disable=SC2269
PELORUS_NAMESPACE="${PELORUS_NAMESPACE}"
function ogn() { printf "oc get --namespace %s $*\n" "${PELORUS_NAMESPACE}"; oc get --namespace "${PELORUS_NAMESPACE}" "$@"; }
function ogns() { printf "oc get --namespace %s svc $*\n" "${PELORUS_NAMESPACE}"; oc get --namespace "${PELORUS_NAMESPACE}" svc "$@"; }
function ornds() { printf "oc rollout status --namespace %s deployments $*\n" "${PELORUS_NAMESPACE}"; oc rollout status --namespace ${PELORUS_NAMESPACE} deployments "$@"; }
function owpr() { printf "oc wait pod --for=condition=Ready -n %s -l pelorus.dora-metrics.io/exporter-type=$*\n" "${PELORUS_NAMESPACE}"; oc wait pod --for=condition=Ready -n ${PELORUS_NAMESPACE} -l pelorus.dora-metrics.io/exporter-type="$*"; }
function owr() { printf "oc wait --for=condition=Ready -n %s $*\n" "${PELORUS_NAMESPACE}"; oc wait --for=condition=Ready -n ${PELORUS_NAMESPACE} "$*"; }
set +a

### Options
OPTIND=1
ENABLE_FAIL_EXP=false
ENABLE_GITLAB_COM_EXP=false
ENABLE_GITEA_COM_EXP=false
ENABLE_BITBUCKET_COM_EXP=false
ENABLE_AZURE_DEVOPS_COM_EXP=false
ENABLE_JIRA_FAIL_EXP=false
ENABLE_JIRA_CUSTOM_FAIL_EXP=false
ENABLE_PAGERDUTY_FAIL_EXP=false
ENABLE_THANOS=false
WEBHOOK_EXP=false
WEBHOOK_WITH_SECRET_EXP=false
ENABLE_ALL_EXPORTERS=false

# Used for cleanup to ensure created binary builds can be safely deleted
BINARY_BUILDS_NAMESPACES=()

while getopts "h?b:d:s:o:f:ae:tc:" option; do
    case "$option" in
    h|\?) print_help;;
    b)    demo_branch=$OPTARG;;
    f)    ci_filename=$OPTARG;;
    o)    demo_org=$OPTARG;;
    d)    venv_dir=$OPTARG;;
    s)    secrets_dir=$OPTARG;;
    e)    enable_exporters=$OPTARG;;
    a)    ENABLE_ALL_EXPORTERS=true;;
    t)    ENABLE_THANOS=true;;
    c)    s3_secrets_dir=$OPTARG;;
    esac
done

if [ -z "${venv_dir}" ]; then
    VENV="${DEFAULT_VENV}"
else
    VENV="${venv_dir}"
fi

if [ -z "${secrets_dir}" ]; then
    SECRETS_DIR="${PROW_SECRETS_DIR}"
else
    SECRETS_DIR="${secrets_dir}"
fi

if [ -z "${s3_secrets_dir}" ]; then
    S3_SECRETS_DIR="${PROW_S3_SECRETS_DIR}"
else
    S3_SECRETS_DIR="${s3_secrets_dir}"
fi

if [ -n "${enable_exporters}" ]; then
    echo ",$enable_exporters," | grep -q ",failure," && ENABLE_FAIL_EXP=true && echo "Enabling Failure exporter"
    echo ",$enable_exporters," | grep -q ",gitlab_committime," && ENABLE_GITLAB_COM_EXP=true && echo "Enabling Gitlab committime exporter"
    echo ",$enable_exporters," | grep -q ",gitea_committime," && ENABLE_GITEA_COM_EXP=true && echo "Enabling Gitea committime exporter"
    echo ",$enable_exporters," | grep -q ",bitbucket_committime," && ENABLE_BITBUCKET_COM_EXP=true && echo "Enabling Bitbucket committime exporter"
    echo ",$enable_exporters," | grep -q ",azure-devops-committime," && ENABLE_AZURE_DEVOPS_COM_EXP=true && echo "Enabling Azure devops committime exporter"
    echo ",$enable_exporters," | grep -q ",jira_committime," && ENABLE_JIRA_FAIL_EXP=true && echo "Enabling JIRA failure exporter"
    echo ",$enable_exporters," | grep -q ",jira_custom_committime," && ENABLE_JIRA_CUSTOM_FAIL_EXP=true && echo "Enabling JIRA custom failure exporter"
    echo ",$enable_exporters," | grep -q ",pagerduty_failure," && ENABLE_PAGERDUTY_FAIL_EXP=true && echo "Enabling PagerDuty failure exporter"
    echo ",$enable_exporters," | grep -q ",webhook," && WEBHOOK_EXP=true && echo "Enabling Webhook exporter"
    echo ",$enable_exporters," | grep -q ",webhook_with_secret," && WEBHOOK_WITH_SECRET_EXP=true && echo "Enabling Webhook exporter with '${WEBHOOK_SECRET_TOKEN}' SECRET_TOKEN"
fi

if [ "${ENABLE_ALL_EXPORTERS}" == true ]; then
    ENABLE_FAIL_EXP=true && echo "Enabling Failure exporter"
    ENABLE_GITLAB_COM_EXP=true && echo "Enabling Gitlab committime exporter"
    ENABLE_GITEA_COM_EXP=true && echo "Enabling Gitea committime exporter"
    ENABLE_BITBUCKET_COM_EXP=true && echo "Enabling Bitbucket committime exporter"
    ENABLE_AZURE_DEVOPS_COM_EXP=true && echo "Enabling Azure devops committime exporter"
    ENABLE_JIRA_FAIL_EXP=true && echo "Enabling JIRA failure exporter"
    ENABLE_JIRA_CUSTOM_FAIL_EXP=true && echo "Enabling JIRA custom failure exporter"
    ENABLE_PAGERDUTY_FAIL_EXP=true && echo "Enabling PagerDuty failure exporter"
    WEBHOOK_EXP=true && echo "Enabling Webhook exporter"
    WEBHOOK_WITH_SECRET_EXP=true && echo "Enabling Webhook exporter with '${WEBHOOK_SECRET_TOKEN}' SECRET_TOKEN"
fi

if [ -z "${demo_branch}" ]; then
    demo_branch="master"
fi

if [ -z "${demo_org}" ]; then
    demo_org="konveyor"
fi

if [ -z "${ci_filename}" ]; then
    ci_filename="values.yaml"
fi

if ! type oc &> /dev/null; then
    echo "OpenShift CLI is necessary to run the script."
    exit 1
fi

if ! type helm &> /dev/null; then
    echo "helm is necessary to run the script."
    exit 1
fi

if ! oc whoami &> /dev/null; then
    echo "You must be logged in to your cluster as an admin to run the script."
    exit 1
fi

if oc get namespace "${PELORUS_NAMESPACE}" &> /dev/null; then
    echo "Namespace ${PELORUS_NAMESPACE} already exists. Delete it before running the script again."
    exit 1
fi

### MAIN

echo "===== 1. Set up deployment ====="

# Create download directory
DWN_DIR=$(TMPDIR="${VENV}" mktemp -d -t "${TMP_DIR_PREFIX}XXXXX") || exit 2

echo "Temporary directory created: ${DWN_DIR}"

# Cleanup download directory on exit
trap 'cleanup_and_exit $?' INT TERM EXIT

download_file_from_url "https://raw.githubusercontent.com/$demo_org/mig-demo-apps/$demo_branch/apps/todolist-mongo-go/pelorus/$ci_filename" "ci_values.yaml" "${DWN_DIR}"
download_file_from_url "https://raw.githubusercontent.com/$demo_org/mig-demo-apps/$demo_branch/apps/todolist-mongo-go/mongo-persistent.yaml" "mongo-persistent.yaml" "${DWN_DIR}"

# Create namespace where pelorus and grafana, prometheus operators will get deployed
oc create namespace "${PELORUS_NAMESPACE}"

# Modify downloaded files
sed -i.bak "s/your_org/$demo_org/g" "${DWN_DIR}/mongo-persistent.yaml"

# Show what has been modified:
diff -uNr "${DWN_DIR}/mongo-persistent.yaml" "${DWN_DIR}/mongo-persistent.yaml.bak"

# Used to create Values Helm file for use with deployment
# that is passed together with other values files as additional
# --values <path_to_thanos_config> parameter
#
# Arguments:
#    $1 - S3 compatible bucket access point
#    $2 - S3 compatible bucket name
#    $3 - S3 compatible bucket access key
#    $4 - S3 compatible bucket secret access key
#
# Return:
#    path to the temporary Helm file that allows to enable Thanos
#
function s3_thanos_tmp() {
    TMP_FILE=$(TMPDIR="${DWN_DIR}" mktemp -t "XXXXX.thanos.pelorus.yaml")
    local bucket_access_point=$1
    local thanos_bucket_name=$2
    local bucket_access_key=$3
    local bucket_secret_access_key=$4

cat <<EOF >> "${TMP_FILE}"
thanos_bucket_name: $thanos_bucket_name
bucket_access_point: $bucket_access_point
bucket_access_key: $bucket_access_key
bucket_secret_access_key: $bucket_secret_access_key
EOF

    echo "${TMP_FILE}"
}

function create_s3_thanos_config() {
    local env_s3_host=$1
    local env_s3_bucket=$2
    local env_s3_access_key=$3
    local env_s3_secret_key=$4

    thanos_config_filepath=""
    # Either pass everything as env variables or as files inside s3 secret folder
    if [[ -n ${!env_s3_host} ]] && [[ -n ${!env_s3_bucket} ]] && \
       [[ -n ${!env_s3_access_key} ]] && [[ -n ${!env_s3_secret_key} ]]; then
         echo "Getting S3 bucket credentials and access data from the env variables" 1>&2
         thanos_config_filepath=$( s3_thanos_tmp "${!env_s3_host}" "${!env_s3_bucket}" "${!env_s3_access_key}" "${!env_s3_secret_key}" )
    elif [ -r "${S3_SECRETS_DIR}/${env_s3_host}" ] && [ -r "${S3_SECRETS_DIR}/${env_s3_bucket}" ] && \
         [ -r "${S3_SECRETS_DIR}/${env_s3_access_key}" ] && [ -r "${S3_SECRETS_DIR}/${env_s3_secret_key}" ]; then
         echo "Getting S3 bucket credentials and access data from the ${S3_SECRETS_DIR} folder" 1>&2
         thanos_config_filepath=$( s3_thanos_tmp "$( cat "${S3_SECRETS_DIR}/${env_s3_host}" )" "$( cat "${S3_SECRETS_DIR}/${env_s3_bucket}" )" \
                               "$( cat "${S3_SECRETS_DIR}/${env_s3_access_key}" )" "$( cat "${S3_SECRETS_DIR}/${env_s3_secret_key}" )" )
    else
        echo "ERROR: Thanos could not be used, due to missing secret values, exiting..." 1>&2
        echo "${thanos_config_filepath}"
        exit 1
    fi

    # Ensure path is set and file is readable
    if [[ -n "${thanos_config_filepath}" ]] && [ -r "${thanos_config_filepath}" ]; then
        echo "${thanos_config_filepath}"
    else
        echo "ERROR: Thanos config file can not be read, exiting..." 1>&2
        exit 1
    fi
}

# Used to create secret temporary file that is used with oc apply
# command. This is to ensure API Tokens are hidden from the terminal
# output.
#
# Arguments:
#    $1 - namespace for which secret will be applied, e.g. pelorus
#    $2 - secret name, e.g. github-secret
#    $3 - api token value
#    $4 - (Optional) - api user name. Not all API tokens require corresponding user.
#
# Return:
#    path to the temporary secret file
#
function mksecret_temp() {
    TMP_FILE=$(TMPDIR="${DWN_DIR}" mktemp -t "XXXXX.pelorus.yaml")
    local secret_namespace=$1
    local secret_name=$2
    local api_token=$3
    local api_user=$4

# We store values under multiple value names to satisfy different exporter types.
# e.g. API_USER is used in the failure exporter while USER in commit time
cat <<EOF >> "${TMP_FILE}"
apiVersion: v1
kind: Secret
metadata:
  name: $secret_name
  namespace: $secret_namespace
type: Opaque
stringData:
  API_TOKEN: $api_token
  TOKEN: $api_token
EOF

    if [[ -n ${api_user} ]]; then
        echo "  USER: $api_user" >> "${TMP_FILE}"
        echo "  API_USER: $api_user" >> "${TMP_FILE}"
    fi

    echo "${TMP_FILE}"
}

function create_k8s_secret() {
    local secret_name=$1
    local env_token_name=$2
    local env_user_name="${3:-NO_USERNAME_DEFINED_VAR}"

    SECRET_CONFIGURED=false
    oc -n $PELORUS_NAMESPACE get secret "${secret_name}"
    secret_present=$?
    if [[ $secret_present = 0 ]]; then
        echo "Secret $secret_name was found"
        SECRET_CONFIGURED=true
    else
      echo "Secret $secret_name was not found, checking env variables to create one"
      secret_filepath=""
      # TOKEN must always be set, USER may be required depending on the backend type
      if [[ -n ${!env_token_name} ]] && [[ -n ${!env_user_name} ]]; then
          echo "API Token and user passed from env var"
          secret_filepath=$( mksecret_temp "$PELORUS_NAMESPACE" "$secret_name" "${!env_token_name}" "${!env_user_name}" )
      elif [[ -n ${!env_token_name} ]]; then
          echo "API Token passed from env var"
          secret_filepath=$( mksecret_temp "$PELORUS_NAMESPACE" "$secret_name" "${!env_token_name}" )
      elif [ -r "${SECRETS_DIR}/${env_token_name}" ] && [ -r "${SECRETS_DIR}/${env_user_name}" ]; then
          echo "Getting API TOKEN and API USER from secrets mounted directory"
          secret_filepath=$( mksecret_temp "$PELORUS_NAMESPACE" "$secret_name" "$( cat "${SECRETS_DIR}/${env_token_name}" )" "$( cat "${SECRETS_DIR}/${env_user_name}" )" )
      elif [ -r "${SECRETS_DIR}/${env_token_name}" ]; then
          echo "Getting API TOKEN from secrets mounted directory"
          secret_filepath=$( mksecret_temp "$PELORUS_NAMESPACE" "$secret_name" "$( cat "${SECRETS_DIR}/${env_token_name}" )" )
      else
          echo "ERROR: API Token for ${secret_name} not provided, exiting..."
          exit 1
      fi
      # Ensure path is set and file is readable
      if [[ -n "${secret_filepath}" ]] && [ -r "${secret_filepath}" ]; then
          oc apply -f "${secret_filepath}"
          oc_apply=$?
          if [[ $oc_apply = 0 ]]; then
              echo "Secret $secret_name was added"
              SECRET_CONFIGURED=true
          fi
          rm "${secret_filepath}"
      fi
    fi
    echo "${SECRET_CONFIGURED}"
}

# enable the pelorus failure exporter for github
if [ "${ENABLE_FAIL_EXP}" == true ]; then
    secret_configured=$(create_k8s_secret github-secret TOKEN)
    secret_exit=$?
    echo "${secret_configured}"
    if [[ $secret_exit != 0 ]]; then
        exit 1
    fi

    # uncomment the failure exporter in ci_values.yaml
    if [[ "$secret_configured" == *true ]]; then
        sed -i.bak "s/#@//g" "${DWN_DIR}/ci_values.yaml"
        echo "The pelorus failure exporter has been enabled"
    fi

    # if required update the failure issue github organization
    if [ "$demo_org" != "konveyor" ]; then
        sed -i.bak "s/konveyor\/mig-demo-apps/$demo_org\/mig-demo-apps/g" "${DWN_DIR}/ci_values.yaml"
    fi
fi

# enable gitlab committime exporter
if [ "${ENABLE_GITLAB_COM_EXP}" == true ]; then
    secret_configured=$(create_k8s_secret gitlab-secret GITLAB_API_TOKEN)
    secret_exit=$?
    echo "${secret_configured}"
    if [[ $secret_exit != 0 ]]; then
        exit 1
    fi
    # uncomment the gitlab committime exporter in ci_values.yaml
    if [[ "$secret_configured" == *true ]]; then
        sed -i.bak "s/#gitlab-committime@//g" "${DWN_DIR}/ci_values.yaml"
        echo "The pelorus gitlab committime exporter has been enabled"
    fi

    # namespace must much one from ci_values.yaml
    build_ns="gitlab-binary"
    BINARY_BUILDS_NAMESPACES+=("${build_ns}")
    build_uri="https://gitlab.com/mpryc/pelorus-gitlab"
    build_hash="b807fd8e1b2bd1755eca14960e5352fe89ff466e"
    "${BINARY_BUILD_SCRIPT}" -n "${build_ns}" -b "${build_ns}-todolist" -u "${build_uri}" -s "${build_hash}"
fi

# enable gitea committime exporter
if [ "${ENABLE_GITEA_COM_EXP}" == true ]; then
    secret_configured=$(create_k8s_secret gitea-secret GITEA_API_TOKEN)
    secret_exit=$?
    echo "${secret_configured}"
    if [[ $secret_exit != 0 ]]; then
        exit 1
    fi
    # uncomment the gitea committime exporter in ci_values.yaml
    if [[ "$secret_configured" == *true ]]; then
        sed -i.bak "s/#gitea-committime@//g" "${DWN_DIR}/ci_values.yaml"
        echo "The pelorus gitea committime exporter has been enabled"
    fi

    # namespace must much one from ci_values.yaml
    build_ns="gitea-binary"
    BINARY_BUILDS_NAMESPACES+=("${build_ns}")
    build_uri="https://try.gitea.io/mpryc/pelorus-gitea"
    build_hash="897f5c490442e88cc609c241da880128ad02e42b"
    "${BINARY_BUILD_SCRIPT}" -n "${build_ns}" -b "${build_ns}-todolist" -u "${build_uri}" -s "${build_hash}"
fi

# enable bitbucket committime exporter
if [ "${ENABLE_BITBUCKET_COM_EXP}" == true ]; then
    secret_configured=$(create_k8s_secret bitbucket-secret BITBUCKET_API_TOKEN BITBUCKET_API_USER)
    secret_exit=$?
    echo "${secret_configured}"
    if [[ $secret_exit != 0 ]]; then
        exit 1
    fi
    # uncomment the bitbucket committime exporter in ci_values.yaml
    if [[ "$secret_configured" == *true ]]; then
        sed -i.bak "s/#bitbucket-committime@//g" "${DWN_DIR}/ci_values.yaml"
        echo "The pelorus bitbucket committime exporter has been enabled"
    fi

    # namespace must much one from ci_values.yaml
    build_ns="bitbucket-binary"
    BINARY_BUILDS_NAMESPACES+=("${build_ns}")
    build_uri="https://bitbucket.org/michalpryc/pelorus-bitbucket"
    build_hash="e2c4ef00468dfc10aad1bd2d4c9d470160a7f471"
    "${BINARY_BUILD_SCRIPT}" -n "${build_ns}" -b "${build_ns}-todolist" -u "${build_uri}" -s "${build_hash}"
fi

# enable Azure devops committime exporter
if [ "${ENABLE_AZURE_DEVOPS_COM_EXP}" == true ]; then
    secret_configured=$(create_k8s_secret azure-devops-secret AZURE_DEVOPS_TOKEN)
    secret_exit=$?
    echo "${secret_configured}"
    if [[ $secret_exit != 0 ]]; then
        exit 1
    fi
    # uncomment the Azure devops committime exporter in ci_values.yaml
    if [[ "$secret_configured" == *true ]]; then
        sed -i.bak "s/#azure-devops-committime@//g" "${DWN_DIR}/ci_values.yaml"
        echo "The pelorus Azure devops committime exporter has been enabled"
    fi

    # namespace must match one from ci_values.yaml
    build_ns="azure-devops-binary"
    BINARY_BUILDS_NAMESPACES+=("${build_ns}")
    build_uri="https://dev.azure.com/matews1943/test-pelorus/_git/test-pelorus"
    build_hash="5b65e1230f9df517bb38979f8e7743928d715973"
    "${BINARY_BUILD_SCRIPT}" -n "${build_ns}" -b "${build_ns}-todolist" -u "${build_uri}" -s "${build_hash}"
fi

# enable JIRA failure exporter
if [ "${ENABLE_JIRA_FAIL_EXP}" == true ]; then
    secret_configured=$(create_k8s_secret jira-secret JIRA_TOKEN JIRA_USER)
    secret_exit=$?
    echo "${secret_configured}"
    if [[ $secret_exit != 0 ]]; then
        exit 1
    fi
    # uncomment the jira failure exporter in ci_values.yaml
    if [[ "$secret_configured" == *true ]]; then
        sed -i.bak "s/#jira-failure@//g" "${DWN_DIR}/ci_values.yaml"
        echo "The pelorus JIRA failure exporter has been enabled"
    fi
fi

# enable JIRA with custom query failure exporter
# Corresponding JIRA card to test against
# https://pelorustest.atlassian.net/jira/core/projects/FIRST/board?selectedIssue=FIRST-14
if [ "${ENABLE_JIRA_CUSTOM_FAIL_EXP}" == true ]; then
    secret_configured=$(create_k8s_secret jira-secret JIRA_TOKEN JIRA_USER)
    secret_exit=$?
    echo "${secret_configured}"
    if [[ $secret_exit != 0 ]]; then
        exit 1
    fi
    # uncomment the jira failure exporter in ci_values.yaml
    if [[ "$secret_configured" == *true ]]; then
        sed -i.bak "s/#jira-custom-failure@//g" "${DWN_DIR}/ci_values.yaml"
        echo "The pelorus JIRA custom failure exporter has been enabled"
    fi
fi

# enable PagerDuty committime exporter
if [ "${ENABLE_PAGERDUTY_FAIL_EXP}" == true ]; then
    secret_configured=$(create_k8s_secret pagerduty-secret PAGER_DUTY_TOKEN)
    secret_exit=$?
    echo "${secret_configured}"
    if [[ $secret_exit != 0 ]]; then
        exit 1
    fi
    # uncomment the PagerDuty failure exporter in ci_values.yaml
    if [[ "$secret_configured" == *true ]]; then
        sed -i.bak "s/#pagerduty_failure@//g" "${DWN_DIR}/ci_values.yaml"
        echo "The pelorus PagerDuty failure exporter has been enabled"
    fi
fi


# enable Webhook exporter
if [ "${WEBHOOK_EXP}" == true ]; then
    # uncomment the Webhook exporter in ci_values.yaml
    sed -i.bak "s/#webhook@//g" "${DWN_DIR}/ci_values.yaml"
    echo "The pelorus Webhook exporter has been enabled"
fi

# enable Webhook exporter that is configured to use SECRET_TOKEN
if [ "${WEBHOOK_WITH_SECRET_EXP}" == true ]; then
    # uncomment the Webhook exporter in ci_values.yaml
    sed -i.bak "s/#webhook_with_secret@//g" "${DWN_DIR}/ci_values.yaml"
    echo "The pelorus Webhook exporter with '${WEBHOOK_SECRET_TOKEN}' SECRET_TOKEN has been enabled"
fi

echo "===== 2. Set up OpenShift resources ====="

# We do check for the exit status, as we are not really interested in the
# current state, e.g. Active of that namespace before deleting resources.
if oc get namespace mongo-persistent 2>/dev/null; then
    oc delete -f "${DWN_DIR}/mongo-persistent.yaml"
fi

# Delete mongo-persistent-scc (securitycontextconstraints.security.openshift.io)
# which may be left from previous runs.
if oc get scc mongo-persistent-scc 2>/dev/null; then
    oc delete scc mongo-persistent-scc
fi

# From now on, exit if something goes wrong
set -e

# If this is a pull request from pelorus
if [ "${REPO_NAME}" == "pelorus" ]; then
    # Check if PULL_NUMBER exists and it's actual number
    if [ ${PULL_NUMBER+x} ] && [[ $PULL_NUMBER =~ ^[0-9]+$ ]]; then
        echo "Provided PULL_NUMBER: '$PULL_NUMBER'"
        sed -i "s/source_ref:.*/source_ref: refs\/pull\/${PULL_NUMBER}\/head/" "${DWN_DIR}/ci_values.yaml"
    fi
fi

# Ensure we are in the top-level directory of pelorus project
pushd "${SCRIPT_DIR}/../"

# Apply config maps for the exporters
# disable for now, as it's divergent from the install instructions.
# oc apply -f "charts/pelorus/configmaps"

helm install operators charts/operators --namespace pelorus --debug --wait --wait-for-jobs

# Wait for grafana and prometheus deployments to be rolled out
retry 5m 1s ornds prometheus-operator
retry 5m 1s ornds grafana-operator-controller-manager

helm install pelorus charts/pelorus --namespace pelorus --debug --wait --wait-for-jobs

# check final deployment
retry 5m 5s ogns grafana-service
retry 5m 5s ogns prometheus-operated
retry 5m 5s ogns prometheus-pelorus

# Print ci_values.yaml for easy debug
cat "${DWN_DIR}/ci_values.yaml"

# Thanos and s3 support
THANOS_HELM_FLAG=() # an array so expanding it later will be 0 words if empty
if [ "${ENABLE_THANOS}" == true ]; then
    echo "Enabling Thanos support"
    thanos_config_file=$(create_s3_thanos_config  s3_host s3_bucket s3_access_key s3_secret_key)
    THANOS_HELM_FLAG=("--values" "${thanos_config_file}")
fi

# update exporter values and helm upgrade
echo helm upgrade pelorus charts/pelorus --namespace pelorus --values "${DWN_DIR}/ci_values.yaml" "${THANOS_HELM_FLAG[@]}"
helm upgrade pelorus charts/pelorus --namespace pelorus --values "${DWN_DIR}/ci_values.yaml" "${THANOS_HELM_FLAG[@]}"

retry 10m 5s owpr deploytime
retry 10m 5s owpr committime

oc create -f "${DWN_DIR}/mongo-persistent.yaml"

retry 4m 5s oc wait pod --for=condition=Ready -n mongo-persistent -l app=mongo
retry 10m 10s oc wait pod --for=condition=Ready -n mongo-persistent -l app=todolist

# Ugly, but let's check if this improves CI
sleep 60

for exporter_pod in $(oc get pods -n pelorus  -l 'pelorus.dora-metrics.io/exporter-type in (committime,failure,deploytime)' -o name);
do
    retry 5m 5s owr "$exporter_pod"
done

# Test all deployed exporters

echo "===== 3. Test Exporters ====="

function send_payload() {
    local exporter_name=$1
    local secret_value="${2:-}"

    webhook_route=$(oc get route "${exporter_name}" -n "${PELORUS_NAMESPACE}" --template='{{ .spec.host }}')

    current_timestamp=$(date +%s)

    header_user_agent="User-Agent: Pelorus-Webhook/e2e"
    header_pelorus_event="X-Pelorus-Event: deploytime"
    header_content="Content-Type: application/json"

    payload_data=$(cat <<EOF
{
    "app": "mongo-todolist",
    "image_sha": "sha256:af4092ccbfa99a3ec1ea93058fe39b8ddfd8db1c7a18081db397c50a0b8ec77d",
    "namespace": "mongo-persistent",
    "timestamp": "$current_timestamp"
}
EOF
    )

    if [ -n "$secret_value" ]; then
        SHA256_HASH_SIGNATURE=$(echo "${payload_data}" | tr -d '[:space:]' | openssl dgst -sha256 -hmac "${secret_value}"| cut -d ' ' -f 2)
        header_secret_token="X-Hub-Signature-256: sha256=${SHA256_HASH_SIGNATURE}"
        curl -X POST \
            -H "$header_user_agent" \
            -H "$header_pelorus_event" \
            -H "$header_content" \
            -H "$header_secret_token" \
            -d "$payload_data" \
            "${webhook_route}/pelorus/webhook"
    else
        curl -X POST \
            -H "$header_user_agent" \
            -H "$header_pelorus_event" \
            -H "$header_content" \
            -d "$payload_data" \
            "${webhook_route}/pelorus/webhook"
    fi
}

# Send some data to the Webhook exporter
if [ "${WEBHOOK_EXP}" == true ]; then
    send_payload "${WEBHOOK_EXPORTER_NAME}"
fi

# Send some data to the Webhook exporter with SECRET_TOKEN
if [ "${WEBHOOK_WITH_SECRET_EXP}" == true ]; then
    send_payload "${WEBHOOK_EXPORTER_WITH_SECRET_NAME}" "${WEBHOOK_SECRET_TOKEN}"
fi

any_exporter_failed=""
exporters=$(oc get route -n "${PELORUS_NAMESPACE}"|grep "-exporter")
echo "$exporters"
for exporter_route in $(echo "$exporters" | awk '{print $2}');
do
    echo "$exporter_route"
    route_output="$(curl "$exporter_route")"
    curl_result=$?
    echo "$route_output"
    if [[ $curl_result -ne 0 ]]; then
        echo "Error curling $exporter_route" 1>&2
        any_exporter_failed=true
    elif ! { echo "$route_output" | grep todolist; }; then
        echo "todolist not found in $exporter_route" 1>&2
        any_exporter_failed=true
    fi
done

if [[ "$any_exporter_failed" = "true" ]]; then
    exit 2
fi

if oc get pods -n pelorus | grep -q Crash ; then
    echo "Some pods are not functioning properly"
    oc get pods -n pelorus
    exit 1
fi

# Validate Thanos, by querying thanos-query with the known data, 20 years from now should be sufficient and should
# not be greater then this CI setup ;)
if [ "${ENABLE_THANOS}" == true ]; then
    THANOS_QUERY_HOST=$(oc get route thanos-pelorus -n pelorus --no-headers -o custom-columns="HOST:spec.host")
    echo "Thanos query host: $THANOS_QUERY_HOST"
    DEPLOY_NO=$(curl -u internal:changeme -k --data-urlencode 'query=count(count_over_time(deploy_timestamp{app="todolist"}[20y]))' "https://${THANOS_QUERY_HOST}/api/v1/query" | jq -r '.data.result[] | [.value]' | grep \" | tr -dc '0-9')
    echo "Deploy count: $DEPLOY_NO"
    if [ "$DEPLOY_NO" -lt "3" ]; then
        echo "Thanos and s3 data is not as expected"
        exit 1
    fi
fi
