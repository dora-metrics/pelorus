# Pelorus Demo

## Demo Assumptions
- Github SSH key is setup on the machine where the demo will run.
- Ansible is installed
- oc command line tools installed
- Logged into OCP Cluster

## Demo Purpose
- Deploy sample application (basic-nginx)
- Make changes to the application (adding a line to index.html)
- commit changes to source control
- redeploy application with the changes to be captured by pelorus

## Demo Prerequisites

Clone the [pelorus repo](https://github.com/redhat-cop/pelorus).

Fork the [RedHat COP Container Pipeline Repo](https://github.com/redhat-cop/container-pipelines), then clone (using ssh).

The location of the repo will be passed as an argument to the pelorus demo script (i.e. /home/<user>/projects/container-pipelines).

in the *seed_hosts.yml* file, change the source_code_url to be your forked repo url
	*container-pipelines/basic-nginx/.applier/group_vars/seed-hosts.yml* file, replace **source_code_url** with the forked repo url
	
Commit these changes back to your fork

## Demo Execution

Run the demo script
``` pelorus/demo/demo.sh <path to container-pipelines> ```
	
The script will create the basic-nginx application by default. After the application is deployed, the script will sleep for 5 minutes to allow the first pipeline to run to completion. Then, a simple line will be added to the index.html file inside of basic-nginx. The changes will be added and commited to source control and the application will build again, rolling out the newest release.





