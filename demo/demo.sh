#!/bin/bash
#Test oc tool
#Assumes User is logged in to cluster

path=$1
url=$2

# Will create spring rest deployment
pushd $path/basic-nginx
   ansible-galaxy install -r requirements.yml --roles-path=galaxy
   ansible-playbook -i ./.applier/ galaxy/openshift-applier/playbooks/openshift-cluster-seed.yml -e skip_manual_promotion=true -e source_code_url=$url
popd

# Run through a loop, so demo presenter can deploy as many sample apps, with commits, as necessary.
v1=$3
while :
do
echo " "
echo " The pipeline and first run of the demo app has started. When it has finished, you may rerun (with commits) or quit now."
echo "1. Rerun with Commit"
echo "2. Quit"
echo -n "Type 1 or 2:"
read -n 1 a
printf "\n"
case $a in
1* )     
echo $v1
#Add Comment to a file to replicate a "change"
echo "this is a comment" >> $path/basic-nginx/index.html

#Change git dir to the one we're changing
export GIT_DIR=$path/.git
export GIT_WORK_TREE=$path

# git commit
pushd $path
  git add .
  git commit  -m "doing a change"
  git push origin master
popd

#Redeploy app
#in the *-build project
oc start-build basic-nginx-pipeline -n basic-nginx-build
;;

2* )     exit 0;;
 
* )     echo "Try again.";;
esac
done

