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


# Function to safely remove temporary files and temporary download dir
# Argument is optional exit value to propagate it after cleanup
function cleanup_and_exit() {
    oc get namespace "${s_build_namespace}"
    namespace_exit=$?
    if [[ $namespace_exit != 0 ]]; then
        echo "Problem getting namespace ${s_build_namespace}"
        exit 1
    fi

    oc delete namespace "${s_build_namespace}"
    namespace_delete=$?
    if [[ $namespace_delete != 0 ]]; then
        echo "Could not delete namespace ${s_build_namespace}"
        exit 1
    fi

    exit 0
}

function print_help() {
    printf "\nUsage: %s [OPTION]... -n [NAMESPACE] -b [APP_NAME]\n\n" % "$0"
    printf "\tStartup:\n"
    printf "\t  -h\tprint this help\n"
    printf "\n\tOptions:\n"
    printf "\t  -c\tclean up binary build (by removing provided namespace)\n"
    printf "\t  -n\tnamespace\n"
    printf "\t  -b\tbinary build app name\n"
    printf "\t  -u\tgit uri to be used for annotation\n"
    printf "\t  -s\tgit commit hash to be used for annotation\n"

    exit 0
}

s_cleanup=false

while getopts "h?cb:n:u:s:" option; do
    case "$option" in
    h|\?) print_help;;
    c)    s_cleanup=true;;
    n)    s_build_namespace=$OPTARG;;
    b)    s_build_app_name=$OPTARG;;
    u)    s_git_uri=$OPTARG;;
    s)    s_git_hash=$OPTARG;;

    esac
done

if [ -z "${s_build_namespace}" ]; then
    print_help
fi

if [ "${s_cleanup}" == true ]; then
    cleanup_and_exit
fi

# build_app_name is not required for cleanup, however we do need
# app name, git hash and git uri
if [ -z "${s_build_app_name}" ] || [ -z "${s_git_hash}" ] || [ -z "${s_git_uri}" ]; then
    print_help
fi

# We do not want to manually remove the built namespace.
# The calling script for the e2e tests makes use of builds
# trap 'cleanup_and_exit $?' INT TERM EXIT

# Create namespace in which build will happen
oc create namespace "${s_build_namespace}"

oc new-build --namespace="${s_build_namespace}" python --name="${s_build_app_name}" --binary=true
oc label --namespace="${s_build_namespace}" bc "${s_build_app_name}" app.kubernetes.io/name="${s_build_app_name}"

# To ensure ./app.py is found
pushd "$(dirname "$0")" || exit 1
oc start-build --namespace="${s_build_namespace}" bc/"${s_build_app_name}" --from-file=./app.py --follow
popd || exit 1

set -x
oc annotate build --namespace="${s_build_namespace}" "${s_build_app_name}"-1 --overwrite \
io.openshift.build.commit.id="${s_git_hash}" \
io.openshift.build.source-location="${s_git_uri}"

echo "SUCCESS"
