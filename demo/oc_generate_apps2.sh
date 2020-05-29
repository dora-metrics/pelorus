#!/bin/bash
#Test oc tool
#Assumes User is logged in to cluster


# Will create spring rest deployment
cd ~/projects/container-pipelines/basic-nginx
ansible-playbook -i ./.applier/ galaxy/openshift-applier/playbooks/openshift-cluster-seed.yml


# Wait a bit (5 min) for the app to be finished deployed
sleep 300

#Add Comment to a file to replicate a "change"
echo "this is a comment" >> /home/kenwilli/projects/container-pipelines/basic-nginx/index.html

#Change git dir to the one we're changing
export GIT_DIR=/home/kenwilli/projects/container-pipelines/.git
export GIT_WORK_TREE=/home/kenwilli/projects/container-pipelines/

# git commit
git add .
git commit -m "doing a change"
git push origin master

#Redeploy app
#in the *-build project
oc project basic-nginx-build
oc start-build basic-nginx-pipeline
