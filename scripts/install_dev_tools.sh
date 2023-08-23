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

# Get the full absolute path to the script. Needed while calling the script
# via various partial paths or sourcing the file from shell
# BASH_SOURCE[0] is safer then $0 when sourcing.
# We enter the dirname of the invoked script and then get the current
# path of the script using pwd
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
# Match the .venv created by the Makefile
DEFAULT_VENV="${SCRIPT_DIR}/../.venv"

TMP_DIR_PREFIX="pelorus_tmp_"

HELM_INSTALL_SCRIPT="https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3"
# Used to download HELM version if git API failed with providing correct one
HELM_FALLBACK_VERSION="v3.9.2"

# Bats are required for conftest
BATS_REPO_URL="https://github.com/bats-core/bats-core"



function download_file_from_url() {
    local url=$1
    local dest_folder=$2

    pushd "${dest_folder}" || exit
      echo "Downloading file: ${url}"
      echo "To: ${dest_folder}"
      curl -LO "${url}"
    popd || exit
}

function extract_file_to_dir() {
    local file_path=$1
    local dest_dir=$2
    local file_names=$3 # Extract only specific files

    if [ ! -f "${file_path}" ]; then
        echo "extract_file_to_dir(): File does not exists: ${file_path}" >&2
        return 2
    fi

    if [ ! -d "${dest_dir}" ]; then
        echo "extract_file_to_dir(): Dest dir does not exists: ${dest_dir}" >&2
        return 2
    fi

    # shellcheck disable=SC2086 # We need to expand $file_names
    tar xvzf "${file_path}" -C "${dest_dir}" ${file_names}
}

# Installs helm into .venv path
function install_helm() {
    local helm_install_script=$1
    local dest_dir=$2
    if [ ! -f "${helm_install_script}" ]; then
        echo "install_helm(): File does not exists: ${helm_install_script}" >&2
        return 2
    fi

    if [ ! -d "${dest_dir}" ]; then
        echo "install_helm(): Dest dir does not exists: ${dest_dir}" >&2
        return 2
    fi

    chmod +x "${helm_install_script}" 
    HELM_INSTALL_DIR="${dest_dir}" USE_SUDO=false VERIFY_CHECKSUM=false "${helm_install_script}"
    helm_install=$?
    type helm
    helm_installed=$?
    if [ $helm_install -ne 0 ] || [ $helm_installed -ne 0 ]; then
        echo "Installing fallback HELM version"
        HELM_INSTALL_DIR="${dest_dir}" USE_SUDO=false VERIFY_CHECKSUM=false "${helm_install_script}" --version "${HELM_FALLBACK_VERSION}"
    fi
}

# Function to check if particular cli binary should be installed
# it checks cli name from arg against array from the passed to this
# script via optarg list of cli's to be installed
function should_cli_be_installed(){
    local cli_check=$1
    local cli_array=("${@:2}")
    # No cli_array is set, accept all CLIs
    if [ -z "${cli_array[*]}" ]; then
        return 0
    fi
    for cli in "${cli_array[@]}"; do
        if [ "$cli" == "$cli_check" ]; then
            return 0
        fi
    done
    return 2
}

# Function to safely remove temporary files and temporary download dir
# Argument is optional exit value to propagate it after cleanup
function cleanup_and_exit() {
    local exit_val=${1:-1}
    if [ -z "${DWN_DIR}" ]; then
        echo "cleanup_and_exit(): Temp download dir not provided !" >&2
    else
      # Ensure dir exists and starts with prefix
      if [ -d "${DWN_DIR}" ]; then
          PELORUS_TMP_DIR=$(basename "${DWN_DIR}")
          if [[ "${PELORUS_TMP_DIR}" =~ "${TMP_DIR_PREFIX}"* ]]; then
              echo "Cleaning up temporary files"
              rm -rf -- "${DWN_DIR}"
          fi
      fi
    fi
    trap - EXIT
    exit "$exit_val"
}

function print_help() {
    printf "\nUsage: %s [OPTION]... -v [DIR]\n\n" % "$0"
    printf "\tStartup:\n"
    printf "\t  -h\tprint this help\n"
    printf "\n\tOptions:\n"
    printf "\t  -c\tcomma separated list of CLI tools e.g. ct,oc\n"
    printf "\t  -v\tpath to virtualenv DIR\n"

    exit 0
}

### Options
OPTIND=1
while getopts "c:h?v:" option; do
    case "$option" in
    h|\?) print_help;;
    c)    cli_tools=$OPTARG;;
    v)    venv_dir=$OPTARG;;
    esac
done

if [ -z "${venv_dir}" ]; then
    VENV="${DEFAULT_VENV}"
else
    VENV="${venv_dir}"
fi

# Get the list of CLI tools to be installed from comma separated output
# Remove any whitespace which user may have added before or after ","
cli_tools_arr=("${cli_tools//' '/}")

# shellcheck disable=SC2206
cli_tools_arr=(${cli_tools_arr//','/ })

# Create download directory inside virtual env dir
DWN_DIR=$(TMPDIR="${VENV}" mktemp -d -t "${TMP_DIR_PREFIX}XXXXX") || exit 2

trap 'cleanup_and_exit' INT TERM EXIT

# Helm install
if should_cli_be_installed "helm" "${cli_tools_arr[@]}" && \
    ! [ -x "$(command -v "${VENV}/bin/helm")" ]; then
      echo "Installing helm CLI to: ${VENV}/bin/helm"
      download_file_from_url "${HELM_INSTALL_SCRIPT}" "${DWN_DIR}"
      HELM_SCRIPT="${DWN_DIR}"/$(basename "${HELM_INSTALL_SCRIPT}")
      install_helm "${HELM_SCRIPT}" "${VENV}/bin"
fi

# Tekton install
if should_cli_be_installed "tkn" "${cli_tools_arr[@]}" && \
    ! [ -x "$(command -v "${VENV}/bin/tkn")" ]; then
      echo "Installing tkn CLI to: ${VENV}/bin/tkn"
      TKN_CLIENT_URL=$("${SCRIPT_DIR}/get_tool_dl_url.py" tkn) \
                    || cleanup_and_exit 2
      echo "$TKN_CLIENT_URL"
      download_file_from_url "${TKN_CLIENT_URL}" "${DWN_DIR}"
      TKN_CLIENT_PATH="${DWN_DIR}"/$(basename "${TKN_CLIENT_URL}")
      extract_file_to_dir "${TKN_CLIENT_PATH}" "${VENV}/bin/" "tkn"
fi

# OC install
if should_cli_be_installed "oc" "${cli_tools_arr[@]}" && \
    ! [ -x "$(command -v "${VENV}/bin/oc")" ]; then
      echo "Installing oc CLI to: ${VENV}/bin/oc"
      OCP_CLIENT_URL=$("${SCRIPT_DIR}/get_tool_dl_url.py" oc) \
                    || cleanup_and_exit 2
      download_file_from_url "${OCP_CLIENT_URL}" "${DWN_DIR}"
      OCP_CLIENT_PATH="${DWN_DIR}"/$(basename "${OCP_CLIENT_URL}")
      # We are interested only in oc/kubectl binaries
      extract_file_to_dir "${OCP_CLIENT_PATH}" "${VENV}/bin/" "oc kubectl"
fi

# CT install
if should_cli_be_installed "ct" "${cli_tools_arr[@]}" && \
    ! [ -x "$(command -v "${VENV}/bin/ct")" ]; then
      CT_CLIENT_URL=$("${SCRIPT_DIR}/get_tool_dl_url.py" ct) \
                    || cleanup_and_exit 2
      echo "$CT_CLIENT_URL"
      download_file_from_url "${CT_CLIENT_URL}" "${DWN_DIR}"
      CT_CLIENT_PATH="${DWN_DIR}"/$(basename "${CT_CLIENT_URL}")
      extract_file_to_dir "${CT_CLIENT_PATH}" "${VENV}/bin/" "ct"
fi

# Promtool install
if should_cli_be_installed "promtool" "${cli_tools_arr[@]}" && \
    ! [ -x "$(command -v "${VENV}/bin/promtool")" ]; then
      PROMTOOL_CLIENT_URL=$("${SCRIPT_DIR}/get_tool_dl_url.py" promtool) \
                    || cleanup_and_exit 2
      echo "$PROMTOOL_CLIENT_URL"
      download_file_from_url "${PROMTOOL_CLIENT_URL}" "${DWN_DIR}"
      CT_CLIENT_PATH="${DWN_DIR}"/$(basename "${PROMTOOL_CLIENT_URL}")
      # promtool is in the dir with same name as tar, we need to
      # extract this to pass to the tar command as wildcards are not
      # supported on every system (e.g. in github actions)
      DIR_NAME=$(basename "${CT_CLIENT_PATH}" | sed 's/\.tar\.gz//g')
      extract_file_to_dir "${CT_CLIENT_PATH}" "${VENV}/bin/" "${DIR_NAME}/promtool"
      mv "${VENV}/bin/${DIR_NAME}/promtool" "${VENV}/bin/"
      rmdir "${VENV}/bin/${DIR_NAME}"
fi

# Conftest CLI
if should_cli_be_installed "conftest" "${cli_tools_arr[@]}" && \
    ! [ -x "$(command -v "${VENV}/bin/conftest")" ]; then
      CONFTEST_CLIENT_URL=$("${SCRIPT_DIR}/get_tool_dl_url.py" conftest) \
                    || cleanup_and_exit 2
      echo "$CONFTEST_CLIENT_URL"
      download_file_from_url "${CONFTEST_CLIENT_URL}" "${DWN_DIR}"
      CONFTEST_CLIENT_PATH="${DWN_DIR}"/$(basename "${CONFTEST_CLIENT_URL}")
      extract_file_to_dir "${CONFTEST_CLIENT_PATH}" "${VENV}/bin/" "conftest"
fi

# Install bats via repository
if should_cli_be_installed "bats" "${cli_tools_arr[@]}" && \
    ! [ -x "$(command -v "${VENV}/bin/bats")" ]; then
    if ! [ -x "$(command -v git)" ]; then
        echo "git command not found"
        exit 2
    fi
    # Get the absolute path of VENV. This should be platform independent
    pushd "${VENV}" || exit
      ABS_VENV_PATH=$(pwd)
    popd || exit
    pushd "${DWN_DIR}" || exit
      git clone "${BATS_REPO_URL}" bats-core-upstream
      pushd bats-core-upstream || exit
        ./install.sh "${ABS_VENV_PATH}"
      popd || exit
      rm -rf bats-core-upstream
    popd || exit
fi

# nooba CLI
if should_cli_be_installed "noobaa" "${cli_tools_arr[@]}" && \
    ! [ -x "$(command -v "${VENV}/bin/noobaa")" ]; then
      NOOBAA_CLIENT_URL=$("${SCRIPT_DIR}/get_tool_dl_url.py" noobaa) \
                    || cleanup_and_exit 2
      echo "$NOOBAA_CLIENT_URL"
      download_file_from_url "${NOOBAA_CLIENT_URL}" "${DWN_DIR}"
      NOOBAA_CLIENT_PATH="${DWN_DIR}"/$(basename "${NOOBAA_CLIENT_URL}")
      extract_file_to_dir "${NOOBAA_CLIENT_PATH}" "${VENV}/bin/"
      mv "${VENV}/bin/noobaa-operator" "${VENV}/bin/noobaa"
fi

if should_cli_be_installed "operator-sdk" "${cli_tools_arr[@]}" && \
    ! [ -x "$(command -v "${VENV}/bin/operator-sdk")" ]; then
      OPERATOR_SDK_URL=$("${SCRIPT_DIR}/get_tool_dl_url.py" operator-sdk) \
                    || cleanup_and_exit 2
      echo "$OPERATOR_SDK_URL"
      download_file_from_url "${OPERATOR_SDK_URL}" "${DWN_DIR}"
      mv "${DWN_DIR}"/operator-sdk_* "${VENV}/bin/operator-sdk"
      chmod +x "${VENV}/bin/operator-sdk"
fi

# cli_shellcheck install
if should_cli_be_installed "shellcheck" "${cli_tools_arr[@]}" && \
    ! [ -x "$(command -v "${VENV}/bin/shellcheck")" ]; then
      SHELLCHECK_URL=$("${SCRIPT_DIR}/get_tool_dl_url.py" shellcheck) \
                    || cleanup_and_exit 2
      echo "$SHELLCHECK_URL"
      download_file_from_url "${SHELLCHECK_URL}" "${DWN_DIR}"
      SHELLCHECK_PATH="${DWN_DIR}"/$(basename "${SHELLCHECK_URL}")
      shellcheck_executable=$(tar -tJf "${SHELLCHECK_PATH}" | grep "/shellcheck")
      tar -xJvf "${SHELLCHECK_PATH}" -C "${DWN_DIR}" "$shellcheck_executable"
      cp "${DWN_DIR}/$shellcheck_executable" "${VENV}/bin/"
fi

if should_cli_be_installed "poetry" "${cli_tools_arr[@]}" && \
    ! [ -x "$(command -v "${DEFAULT_VENV}/bin/poetry")" ]; then
        curl -sSL https://install.python-poetry.org | POETRY_HOME="$DEFAULT_VENV" python3 -
fi

cleanup_and_exit 0