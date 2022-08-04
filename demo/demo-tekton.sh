#!/usr/bin/env bash
#Assumes User is logged in to cluster
set -euo pipefail

Help()
{
   # Display Help
   echo "Execute a tekton pipeline with various build types."
   echo
   echo "Syntax: scriptTemplate [-h|g|b|]"
   echo "options:"
   echo "g     the git url"
   echo "h     Print this Help."
   echo "b     build type [buildconfig, binary, s2i]"
   echo
}

# Get the options
while getopts ":hg:b:" option; do
   case $option in
      h) # display Help
         Help
         exit;;
      g) # Enter the git url
         url=$OPTARG;;
      b) # Enter the build type 
         build_type=$OPTARG;;
     \?) # Invalid option
         echo "Error: Invalid option"
         exit;;
   esac
done

all_cmds_found=0
for cmd in oc tkn; do
   if ! command -v $cmd; then
      echo "No $cmd executable found in $PATH" >&2
      all_cmds_found=1
   fi
done
if ! [[ $all_cmds_found ]]; then exit 1; fi


tekton_setup_dir="$(dirname "${BASH_SOURCE[0]}")/tekton-demo-setup"
python_example_txt="$(dirname "${BASH_SOURCE[0]}")/python-example/response.txt"

echo "Clean up resources prior to execution:"
oc delete buildConfig basic-python-tekton || true

echo "Setting up resources:"

echo "1. Installing tekton operator"
oc apply -f "$tekton_setup_dir/01-tekton-operator.yaml"

echo "2. Setting up python tekton project"
if ! project_setup_output="$(oc apply -f "$tekton_setup_dir/02-project.yaml" 2>&1)"; then
   if echo "$project_setup_output" | grep -q "AlreadyExists"; then
      echo "Project already exists"
   else
      echo "$project_setup_output" >&2
      exit 1
   fi
else
   echo "$project_setup_output"
fi


echo "3. Setting up build and deployment information"
oc process -f "$tekton_setup_dir/03-build-and-deploy.yaml" | oc apply -f -

route="$(oc get -n basic-python-tekton route/basic-python-tekton --output=go-template='http://{{.spec.host}}')"

counter=1

current_branch="$(git symbolic-ref HEAD)"
current_branch=${current_branch##refs/heads/}

function run_pipeline {
   tkn pipeline start -n basic-python-tekton --showlog basic-python-tekton-pipeline \
      -w name=repo,claimName=basic-python-tekton-build-pvc \
      -p git-url="$url" -p git-revision="$current_branch" \
      -p BUILD_TYPE="$build_type"
}

echo -e "\nRunning pipeline\n"
run_pipeline

echo -e "\nWhen ready, page will be available at $route"

while true; do
   echo ""
   echo "The pipeline and first run of the demo app has started. When it has finished, you may rerun (with commits) or quit now."
   echo "1. Rerun with Commit"
   echo "2. Quit"
   read -r -p "Type 1 or 2: " -n 1 a
   echo ""
   case $a in
      1* )
         echo "We've modified this file, time to build and deploy a new version. Times modified: $counter" | tee -a "$python_example_txt"
         git commit -m "modifying python example, number $counter" -- "$python_example_txt"
         git push origin "$current_branch"

         run_pipeline

         echo -e "\nWhen ready, page will be available at $route"

         counter=$((counter+1))
      ;;

      2* ) exit 0 ;;
      * ) echo "I'm not sure what $a means, please give 1 or 2" >&2 ;;
   esac
done

