# Configuring Exporters

Exporters are the bots that gather the data we use to populate the dashboards. First, let's make some data!

## Step 1: Install the dummy application

In order for Pelorus to collect data, we are going to deploy an application pipeline to build and deploy a sample application.  Make your own fork of this sample repository so that you can make changes to it:

https://github.com/kkoller/container-pipelines.git

Clone your fork:

    git clone https://github.com/<Your Repo>/container-pipelines.git
    cd container-pipelines/basic-nginx
    ansible-galaxy install -r requirements.yml -p galaxy

Replace the `source_code_url` variable with your fork repo and `skip_manual_promotion` to `true`, then deploy it.

    sed -i '/source_code_url:/c\source_code_url: https://github.com/<Your Repo>/container-pipelines.git' .applier/group_vars/seed-hosts.yml
    sed -i '/skip_manual_promotion:/c\skip_manual_promotion: true' .applier/group_vars/seed-hosts.yml
    ansible-playbook -i ./.applier/ galaxy/openshift-applier/playbooks/openshift-cluster-seed.yml

Let's take a look at the data points in the app that Pelorus will look to collect.

First, the build.

    oc get builds -l app.kubernetes.io/name -n basic-nginx-build

Wait a few minutes for the app to be promoted, then check application in production.

    oc get pods -l app.kubernetes.io/name -n basic-nginx-prod

In the next few sections, we'll deploy some exporters that collect data in a similar way to these commands.

## Step 2: Inspect your first exporter

### Deploy Time Exporter

`Change into the `pelorus` directory take a look at the exporter defined by default in `charts/pelorus/values.yaml`

    exporters:
      instances:
        # Values file for exporter helm chart
      - app_name: deploytime-exporter
        source_context_dir: exporters/deploytime
        extraEnv:
        - name: APP_FILE
          value: app.py
        source_url: https://github.com/redhat-cop/pelorus.git

We get the information we need about deploy time from OpenShift, so this exporter works out-of-the-box!

## Step 3:

### Commit Time Exporter

This exporter relies on information from Git, and so we have to configure our credentials before we can deploy it.

Confirm you have a [Github Personal Access Token](https://help.github.com/en/github/authenticating-to-github/creating-a-personal-access-token-for-the-command-line)

Use the token information and the command below to generate a Github secret:

    oc create secret generic github-secret \
      --from-literal=GIT_USER=<username> \
      --from-literal=GIT_TOKEN=<personal access token> -n pelorus

Update the `values.yaml` and then upgrade our helm installation of Pelorus to add an additional exporter to the `instances` list:

      - app_name: committime-github
        env_from_secrets:
        - github-secret
        source_context_dir: exporters/committime
        extraEnv:
        - name: APP_FILE
          value: app.py
        source_url: https://github.com/redhat-cop/pelorus.git

      helm upgrade pelorus charts/pelorus --namespace pelorus

Commit some changes to your fork of the sample app repository to see commit data populated in the Pelorus dashboard!

## Failure Exporter

For failures, we need to configure credentials for access to Jira.

Confirm you have a [Jira Personal Access Token](https://id.atlassian.com/manage-profile/security/api-tokens)

Steps:
  - Navigate to Jira
  - Click on your profile picture
  - Account settings
  - Security
  - Create and manage API tokens

Ensure that you save the token upon generation, as it will disapear after closing the dialog box.

Use the token information and the command below to generate a Jira secret:

       oc create secret generic jira-secret \
        --from-literal=SERVER=<Jira Server> \
        --from-literal=USER=<email> \
        --from-literal=TOKEN=<personal access token> \
        --from-literal=PROJECT=<Jira Project> \
        -n pelorus

Once again, we will update our values.yaml and upgrade our Pelorus deployment.

      - app_name: failure-exporter
        env_from_secrets:
        - jira-secret
        source_context_dir: exporters/failure
        extraEnv:
        - name: APP_FILE
          value: app.py
        source_url: https://github.com/redhat-cop/pelorus.git

      helm upgrade pelorus charts/pelorus --namespace pelorus

For Jira, we are all accessing a shared project.  We will create some failure tickets together so that we can see them appear in our dashboard!
