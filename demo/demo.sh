#!/bin/bash
#Test oc tool
#Assumes User is logged in to cluster

path=$1
url=$2

# Will create spring rest deployment
cd $path/basic-nginx
ansible-galaxy install -r requirements.yml --roles-path=galaxy
ansible-playbook -i ./.applier/ galaxy/openshift-applier/playbooks/openshift-cluster-seed.yml -e skip_manual_promotion=true -e source_code_url=$url


# Wait a bit (5 min) for the app to be finished deployed
sleep 300

#Add Comment to a file to replicate a "change"
echo "this is a comment" >> $path/basic-nginx/index.html

#Change git dir to the one we're changing
export GIT_DIR=$path/.git
export GIT_WORK_TREE=$path

# git commit
git add .
git commit -m "doing a change"
git push origin master

#Redeploy app
#in the *-build project
oc start-build basic-nginx-pipeline -n basic-nginx-build
