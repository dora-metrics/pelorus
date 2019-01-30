#!/bin/bash
set -e

SCRIPT_BASE_DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
DEFAULT_JENKINS_NAMESPACE=basic-spring-boot-build
DEFAULT_HYGIEIA_NAMESPACE=hygieia
TEMP_DIRECTORY=temp
HYGIEIA_TOKEN_FILE=hygieia_token.txt
GITEA_REPO_URL_FILE=gitea_repo.txt
SAMPLE_REPO_NAME="mdt-example"
GITEA_ORG_NAME="mdt"

# Process Input
for i in "$@"
do
  case $i in
    -s=*|--subdomain=*)
      OCP_SUBDOMAIN="${i#*=}"
      shift;;
    -g=*|--github-token=*)
      GITHUB_TOKEN="${i#*=}"
      shift;;
    -j=*|--jenkins-namespace-=*)
      JENKINS_NAMESPACE="${i#*=}"
      shift;;
    -h=*|--namespace=*)
      HYGIEIA_NAMESPACE="${i#*=}"
      shift;;
    * )
      echo "Invalid Option"
      exit 1
      ;;
  esac
done


if [ -z "${OCP_SUBDOMAIN}" ]; then
  echo "Error: OpenShift domain must be provided using the `-s` flag!"
  exit 1
fi

if [ -z "${GITHUB_TOKEN}" ]; then
  echo "Error: GitHub token must be provided using the `-g` flag!"
  exit 1
fi

if [ -z "${JENKINS_NAMESPACE}" ]; then
  JENKINS_NAMESPACE="${DEFAULT_JENKINS_NAMESPACE}"
fi

if [ -z "${HYGIEIA_NAMESPACE}" ]; then
  HYGIEIA_NAMESPACE="${DEFAULT_HYGIEIA_NAMESPACE}"
fi

echo
echo "## Provisioning MDT ##"
echo

echo "Downoading Ansible Galaxy Dependencies..."
echo

ansible-galaxy install -r "${SCRIPT_BASE_DIR}/requirements.yml" -p dependencies

echo
echo "Downloading Dependencies..."
echo

ansible-playbook -i localhost, "${SCRIPT_BASE_DIR}/playbooks/prep.yml"

echo
echo "Deploying Hygeia..."
echo

ansible-playbook -i "${SCRIPT_BASE_DIR}/dependencies/containers-quickstarts/hygieia/.applier" "${SCRIPT_BASE_DIR}/playbooks/hygieia.yml" -e filter_tags=all -e k8s_namespace="${HYGIEIA_NAMESPACE}" -e jenkins_namespace="${JENKINS_NAMESPACE}" -e openshift_default_subdomain="${OCP_SUBDOMAIN}" -e github_personal_access_token="${GITHUB_TOKEN}"

echo
echo "Deploying Application Projects..."
echo

ansible-playbook -i "${SCRIPT_BASE_DIR}/dependencies/container-pipelines/basic-spring-boot/.applier" "${SCRIPT_BASE_DIR}/dependencies/openshift-applier/playbooks/openshift-cluster-seed.yml" -e filter_tags=project

echo
echo "Deploying Jenkins..."
echo

repo_url=$(cat vars/mdt.yml | yq '.mdt_git_repositories[] | select(.name == "containers-quickstarts") | .uri')
repo_branch=$(cat vars/mdt.yml | yq '.mdt_git_repositories[] | select(.name == "containers-quickstarts") | .branch')
ansible-playbook -i "${SCRIPT_BASE_DIR}/dependencies/containers-quickstarts/jenkins-masters/hygieia-plugin/.applier" "${SCRIPT_BASE_DIR}/dependencies/openshift-applier/playbooks/openshift-cluster-seed.yml" -e hygieia_token=$(cat "${SCRIPT_BASE_DIR}/${TEMP_DIRECTORY}/${HYGIEIA_TOKEN_FILE}") -e hygieia_url="http://hygieia.${HYGIEIA_NAMESPACE}.${OCP_SUBDOMAIN}/api/"  -e namespace="${JENKINS_NAMESPACE}" -e source_code_url=${repo_url} -e source_code_ref=${repo_branch}

echo
echo "Deploying Application..."
echo

repo_url=$(cat vars/mdt.yml | yq '.mdt_git_repositories[] | select(.name == "container-pipelines") | .uri')
repo_branch=$(cat vars/mdt.yml | yq '.mdt_git_repositories[] | select(.name == "container-pipelines") | .branch')
app_repo_url=$(cat vars/mdt.yml | yq '.sample_app_repo_url')
app_repo_branch=$(cat vars/mdt.yml | yq '.sample_app_repo_ref')
ansible-playbook -i "${SCRIPT_BASE_DIR}/dependencies/container-pipelines/basic-spring-boot/.applier" "${SCRIPT_BASE_DIR}/dependencies/openshift-applier/playbooks/openshift-cluster-seed.yml" -e sb_application_repository_url=${app_repo_url} -e sb_application_repository_ref=${app_repo_branch} -e sb_source_repository_url=${repo_url} -e sb_source_repository_ref=${repo_branch} -e sb_pipeline_script=Jenkinsfile.hygieia

echo
echo "Running Post Deployment Steps..."
echo

ansible-playbook -i localhost, "${SCRIPT_BASE_DIR}/playbooks/post.yml" -e k8s_namespace="${HYGIEIA_NAMESPACE}" -e jenkins_namespace="${JENKINS_NAMESPACE}"
