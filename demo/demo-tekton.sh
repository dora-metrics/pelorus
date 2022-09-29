#!/usr/bin/env bash
#Assumes User is logged in to cluster
set -euo pipefail

app_name="basic-python-tekton"
app_namespace="basic-python-tekton"

Help()
{
   # Display Help
   echo "Execute a tekton pipeline with various build types."
   echo
   echo "Syntax: scriptTemplate [-h|g|b|n]"
   echo "options:"
   echo "a     application name, default ${app_name}"
   echo "n     namespace to be used, default ${app_namespace}"
   echo "g     the git url"
   echo "r     git branch reference, use this for Pull Requests. e.g. refs/pull/587/head"
   echo "h     Print this Help."
   echo "b     build type [buildconfig, binary, s2i]"
   echo "t     Time in seconds to sleep between subsequent deployments, default 300 (enables non-interaction mode)"
   echo "c     Number of deployments, default 1 (enables non-interaction mode)"
   echo
}

# Defaults
current_branch="$(git symbolic-ref HEAD)"
current_branch=${current_branch##refs/heads/}
url=""
build_type="binary"
NO_HUMAN=false
sleep_between=300
no_deployments=1
REMOTE_BRANCH_EXISTS=false
PELORUS_WORKING_DIR=""
PELORUS_DEMO_TMP_DIR=""
TMP_DIR_PREFIX="pelorus_tkn_tmp_"

# Get the options
while getopts ":hg:b:r:n:t:c:a:" option; do
   case $option in
      h) # display Help
         Help
         exit;;
      g) # Enter the git url
         url=$OPTARG;;
      r) # the git ref
         current_branch=$OPTARG;;
      b) # Enter the build type 
         build_type=$OPTARG;;
      t) # Sleep between subsequent deployments
         sleep_between=$OPTARG && \
         NO_HUMAN=true;;
      c) # Number of subsequent deployments
         no_deployments=$OPTARG && \
         NO_HUMAN=true;;
      a) # Application name
         app_name=$OPTARG;;
      n) # Application namespace
         app_namespace=$OPTARG;;
\?) # Invalid option
         echo "Error: Invalid option"
         exit;;
   esac
done

echo "============================"
echo "Executing the ${app_name} demo for Pelorus..."
echo ""
echo "*** Current Options used ***"
echo "App name: ${app_name}"
echo "Used namespace: ${app_namespace}"
if [[ "$url" != "" ]]; then
  echo "Git URL: $url"
else
  echo "Git repository path: $(pwd)"
fi
echo "Git ref: $current_branch"
echo "Build Type: $build_type"
echo "No interaction mode: ${NO_HUMAN}"
if [ "${NO_HUMAN}" == true ]; then
    echo "Number of deployments: ${no_deployments}"
    echo "Time between deployments: ${sleep_between}[s]"
fi
echo "============================"
echo ""

all_cmds_found=0
for cmd in oc tkn; do
   if ! command -v $cmd &> /dev/null; then
      echo "No $cmd executable found in $PATH" >&2
      all_cmds_found=1
   fi
done
if ! [[ $all_cmds_found ]]; then exit 1; fi

tekton_setup_dir="$(dirname "${BASH_SOURCE[0]}")/tekton-demo-setup"
python_example_txt="$(dirname "${BASH_SOURCE[0]}")/python-example/response.txt"

# Fail early if master is being used
if [[ "$current_branch" == "master" ]]; then
  echo "Do not use master branch..."
  exit 1
fi

# Use local directory as url
if [[ "$url" == "" ]] && [[ $(git status --porcelain --untracked-files=no) ]]; then
  echo "Your local repository contains modified files and can not continue..."
  git status --porcelain --untracked-files=no
  exit 1
fi

echo "Discovering Pelorus deployment in the 'pelorus' namespace"
FOUND_COMMITTIME=false
# Check if Pelorus is deployed on the cluster and monitors
# required namespace or default one, which means all of them
COMMITTIME_EXPORTERS=$(oc get pod -n pelorus -l pelorus.konveyor.io/exporter-type=committime --field-selector=status.phase==Running --no-headers -o custom-columns=":metadata.name")
for committime_exporter in $COMMITTIME_EXPORTERS;
do
  committime_namespaces=$(oc exec -n pelorus "${committime_exporter}" -- printenv NAMESPACES)
  echo ",${committime_namespaces},"  | grep ",${app_namespace}," > /dev/null && FOUND_COMMITTIME=true
  echo "${committime_namespaces}"  | grep "default" > /dev/null && FOUND_COMMITTIME=true
done

if [ "${FOUND_COMMITTIME}" == false ]; then
  echo "ERROR: Commit Time exporter for the Pelorus deployment in the 'pelorus' namespace do not"
  echo "       monitor '${app_namespace}' namespace in which you are trying to deploy application."
  echo "       Please correct your Pelorus deployment and restart demo script."
  exit 1
fi

# Function to safely remove temporary files and temporary download dir
# Argument is optional exit value to propagate it after cleanup
function cleanup_and_exit() {
    local exit_val=$1
    if [ -z "${PELORUS_DEMO_TMP_DIR}" ]; then
        echo "cleanup_and_exit(): Temp download dir not provided !" >&2
    else
      # Ensure dir exists and starts with prefix
      if [ -d "${PELORUS_DEMO_TMP_DIR}" ]; then
          PELORUS_TMP_DIR=$(basename "${PELORUS_DEMO_TMP_DIR}")
          if [[ "${PELORUS_TMP_DIR}" =~ "${TMP_DIR_PREFIX}"* ]]; then
              echo "Cleaning up temporary files"
              eval rm -rf "${PELORUS_DEMO_TMP_DIR}/*"
              rmdir "${PELORUS_DEMO_TMP_DIR}"
          fi
      fi
    fi
    # Propagate exit value if was provided
    [ -n "${exit_val}" ] && exit "$exit_val"
    exit 0
}

trap 'cleanup_and_exit 0' INT TERM EXIT

# Check if the remote branch exists
# if url is "" means user want to run script from within local folder
# For the local folder, we prefer to run ls-remote over listing of branches, because
# remote branch may have been removed
if [[ "$url" == "" ]]; then
  if git ls-remote --heads  2>/dev/null | grep "${current_branch}">/dev/null; then
    REMOTE_BRANCH_EXISTS=true
  fi
  # Top level git repository
  PELORUS_WORKING_DIR="$(git rev-parse --show-toplevel)" || exit 1
elif [[ "$url" != "" ]]; then
  # Create temporary directory
  PELORUS_DEMO_TMP_DIR=$( mktemp -d -t "${TMP_DIR_PREFIX}_XXXXX" ) || exit 1
  echo "Pre: Temp directory created: ${PELORUS_DEMO_TMP_DIR}"
  if git ls-remote --heads "${url}" "${current_branch}"  2>/dev/null | grep "${current_branch}">/dev/null; then
    REMOTE_BRANCH_EXISTS=true
  fi
  git clone "${url}" "${PELORUS_DEMO_TMP_DIR}/pelorus"
  pushd "${PELORUS_DEMO_TMP_DIR}/pelorus" || exit 1
    PELORUS_WORKING_DIR="$( git rev-parse --show-toplevel )" || exit 1
  popd
fi

# Ensure we are on the proper branch, if branch is not in remote create one
echo "Pre: Using Pelorus git dir: ${PELORUS_WORKING_DIR}"
pushd "${PELORUS_WORKING_DIR}" || exit 1
  if [ "${REMOTE_BRANCH_EXISTS}" == true ]; then
    echo "Pre: Using existing remote branch: ${current_branch}"
    git fetch origin
    git checkout "${current_branch}"
  elif [ "${REMOTE_BRANCH_EXISTS}" == false ]; then
    echo "Pre: Creating new branch: ${current_branch}"
    git checkout -b "${current_branch}"
    git push --set-upstream origin "${current_branch}"
  else
    echo "ERROR: Remote branch check went terribly wrong, exitting"
    exit 1
  fi
popd || exit 1

# Create namespace if one doesn't exist
if oc get namespace "${app_namespace}" >/dev/null 2>&1 ; then
    echo "1. Namespace '${app_namespace}' already exists"
else
    echo "1. Create namespace: ${app_namespace}"
    oc process -f "$tekton_setup_dir/01-new-project-request_template.yaml" -p PROJECT_NAME="${app_namespace}" | oc create -f -
fi

echo "Clean up resources prior to execution from '${app_namespace}' namespace:"
# cleaning resources vs. deleting the namespace to preserve pipeline run history
# resources are cleaned to ensure that the new running artifact is from the latest build
printf "ImageStream(s): "
oc delete --all imagestream -n "${app_namespace}" 2> /dev/null || echo "...done"
printf "DeploymentConfig: "
oc scale "dc/${app_name}" --replicas=0 -n "${app_namespace}" &> /dev/null || true
oc delete "dc/${app_name}" -n "${app_namespace}" 2> /dev/null || echo "...done"
printf "BuildConfig: "
oc delete buildConfig "${app_name}" -n "${app_namespace}" 2> /dev/null || echo "...done"
printf "Build: "
oc delete "buildconfig.build.openshift.io/${app_name}" -n "${app_namespace}" 2> /dev/null || echo "...done"
printf "Pods: "
oc delete --all pods -n "${app_namespace}"  2> /dev/null || echo "...done"
printf "ReplicationController: "
oc delete --all replicationcontroller -n "${app_namespace}" 2> /dev/null || echo "...done"
printf "Templates: "
oc delete --all template.template.openshift.io -n "${app_namespace}" 2> /dev/null || echo "...done"
printf "RBAC Authorization: "
oc delete "clusterrolebinding.rbac.authorization.k8s.io/pipeline-role-binding-${app_namespace}" 2> /dev/null || echo "...done"
pv="$(oc get pv | grep "${app_name}" | cut -d " " -f 1)"
pvc="$(oc get pvc -n "${app_name}" | cut -d " " -f 1 | tail -n 1)"
printf "Remove PV's and PVC's associated w/ the tekton demo: %s and %s\n" "$pv" "$pvc" 
oc delete pv "$pv" --grace-period=0 --wait=false || true
oc delete pvc "$pvc" -n "${app_namespace}" --grace-period=0 --wait=false || true
oc patch pvc "$pvc" -p '{"metadata":{"finalizers":null}}' -n "${app_namespace}" || true

echo "Setting up resources:"

echo "2. Installing tekton operator"
oc apply -f "$tekton_setup_dir/02-tekton-operator.yaml"

echo "3. Creating pipeline-role ClusterRole"
oc apply -f "$tekton_setup_dir/03-rbac-pipeline-role.yaml"

echo "4. Creating ClusterRoleBinding with ServiceAccount"
oc process -f "$tekton_setup_dir/04-service-account_template.yaml" -p PROJECT_NAMESPACE="${app_namespace}" -n default | oc create -f -

echo "5. Setting up build and deployment information"
pushd "${PELORUS_WORKING_DIR}" || exit 1
  GIT_TKN_BRANCH=$(git symbolic-ref --short HEAD)
  GIT_TKN_URL=$(git config --get remote.origin.url)
  # Tekton does not have ssh certificates, so needs to use http/https
  if [[ "${GIT_TKN_URL}" != http* ]]; then
    if [[ "${GIT_TKN_URL}" == git@* ]]; then
      # Replace git with https:
      #   git@github.com:mpryc/pelorus.git
      #   https://github.com/mpryc/pelorus.git
      GIT_TKN_URL=$( echo "${GIT_TKN_URL}" | sed 's/\:/\//g' | sed 's/git\@/https\:\/\//g' )
    fi
  fi
popd || exit 1

oc process -f "$tekton_setup_dir/05-build-and-deploy.yaml" -p PROJECT_URI="${GIT_TKN_URL}" -p PROJECT_REF="${GIT_TKN_BRANCH}" \
           -p NAMESPACE="${app_namespace}" -p APPLICATION_NAME="${app_name}" \
           -n default > /tmp/05-build-and-deploy.yaml.out 2>/tmp/05-build-and-deploy.yaml.err
oc apply -n "${app_namespace}" -f /tmp/05-build-and-deploy.yaml.out

route=$(oc get -n "${app_namespace}" "route/${app_name}" --output=go-template='http://{{.spec.host}}')

counter=1

function run_pipeline {
    pushd "${PELORUS_WORKING_DIR}" || exit 1
      echo "Running pipeline for the '${GIT_TKN_URL}' repo and '${GIT_TKN_BRANCH}' branch"
      tkn pipeline start -n "${app_namespace}" --showlog "${app_name}-pipeline" \
        -w name=repo,claimName="${app_name}-build-pvc" \
        -p git-url="${GIT_TKN_URL}" -p git-revision="${GIT_TKN_BRANCH}" \
        -p build-no="${counter}" \
        -l app.kubernetes.io/name="${app_name}" \
        -p BUILD_TYPE="$build_type"
    popd || exit 1
}

echo -e "\nRunning pipeline\n"
run_pipeline

echo -e "\nWhen ready, page will be available at $route"

if [ "${NO_HUMAN}" == false ]; then
    while true; do
       echo ""
       echo "The pipeline and first run of the demo app has started. When it has finished, you may rerun (with commits) or quit now."
       echo "1. Rerun with Commit"
       echo "2. Quit"
       read -r -p "Type 1 or 2: " -n 1 a
       echo ""
       case $a in
          1* )
             pushd "${PELORUS_WORKING_DIR}" || exit 1
               echo "We've modified this file, time to build and deploy a new version from ${GIT_TKN_BRANCH} branch and ${GIT_TKN_URL} repo. Times modified: $counter" | tee -a "demo/${python_example_txt}"
               git commit -m "modifying python example, number $counter" -- "demo/${python_example_txt}"
               git push origin "$current_branch"

               counter=$((counter+1))
               run_pipeline

               echo -e "\nWhen ready, page will be available at $route"

             popd || exit 1
          ;;

          2* ) exit 0 ;;
          * ) echo "I'm not sure what $a means, please give 1 or 2" >&2 ;;
       esac
    done
elif [ "${NO_HUMAN}" == true ]; then
    while [ $counter -lt "$no_deployments" ]; do
        pushd "${PELORUS_WORKING_DIR}" || exit 1
          echo "We've modified this file, time to build and deploy a new version from ${GIT_TKN_BRANCH} branch and ${GIT_TKN_URL} repo. Times modified: $counter" | tee -a "demo/${python_example_txt}"
          git commit -m "modifying python example, number $counter" -- "demo/${python_example_txt}"
          git push origin "$current_branch"
          counter=$((counter+1))
          run_pipeline
          echo -e "\nWhen ready, page will be available at $route"
        popd
          # Do not sleep on the last iteration
        if [ $counter -lt "$no_deployments" ]; then
            sleep "$sleep_between"
        fi
    done
fi

echo "Finished. Consider removing remote branch: ${current_branch}"
