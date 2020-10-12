# Configuring Exporters

Exporters are the bots that gather the data we use to populate the dashboards. First, let's make some data!

Step 3: Install the dummy application

    git clone https://github.com/redhat-cop/container-pipelines.git
    cd container-pipelines/basic-spring-boot
    ansible-galaxy install -r requirements.yml -p galaxy
    

1. Set the `app-label`

## Deploy Time Exporter



## Commit Time Exporter

Confirm you have a [Github Personal Access Token](https://help.github.com/en/github/authenticating-to-github/creating-a-personal-access-token-for-the-command-line)

Github secret
    
    oc create secret generic github-secret --from-literal=GIT_USER=<username> --from-literal=GIT_TOKEN=<personal access token> -n pelorus



## Failure Exporter

Confirm you have a [Jira Personal Access Token](https://confluence.atlassian.com/bitbucketserver/personal-access-tokens-939515499.html)

Jira secret

        oc create secret generic jira-secret --from-literal=GIT_USER=<username> --from-literal=GIT_TOKEN=<personal access token> --from-literal=GIT_API=<api> -n pelorus