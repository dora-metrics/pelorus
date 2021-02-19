# Pelorus Samples & Use Cases

## Deploying the Basic-Nginx Sample alongside the Webhook/Generic CommitTime Exporter

1. Fork [this repo](https://github.com/konveyor/pelorus)
2. Run `oc create namespace pelorus`
3. Create a GitHub Personal Access Token and store it as a secret in OCP:
```
oc create secret generic github-secret --from-literal=GIT_USER=<username> --from-literal=GIT_TOKEN=<personal access token> --namespace pelorus
```
4. Run `helm install operators charts/operators --namespace pelorus`
5. Update the values.yaml file with the following:
```
exporters:
  instances:
  - app_name: deploytime-exporter
    source_context_dir: exporters/
    extraEnv:
    - name: APP_FILE
      value: deploytime/app.py
    - name: LOG_LEVEL
      value: DEBUG
    - name: NAMESPACES
      value: basic-nginx-prod
    source_ref: master
    source_url: https://github.com/konveyor/pelorus.git
  - app_name: committime-generic
    env_from_secrets:
    - github-secret
    - mongodb-build-webhook
    source_context_dir: exporters/
    extraEnv:
    - name: APP_FILE
      value: committime/app.py
    - name: LOG_LEVEL
      value: DEBUG
    - name: PROVIDER
      value: webhook
    source_ref: master
    source_url: https://github.com/konveyor/pelorus.git

webhooks:
  instances:
  - app_name: build-webhook
    source_context_dir: webhooks/
    extraEnv:
    - name: APP_FILE
      value: build-webhook/app.py
    - name: LOG_LEVEL
      value: DEBUG
    source_ref: master
    source_url: https://github.com/konveyor/pelorus.git
    mongodb:
      namespace: openshift
      imagestream: "mongodb:3.6"
      memory_limit: 512Mi
```
6. Run `helm install pelorus charts/pelorus --namespace pelorus`
7. Run `cd samples/basic-nginx`
8. Run `ansible-galaxy install -r requirements.yml --roles-path=galaxy`
9. Run `ansible-playbook -i ./.applier/ galaxy/openshift-applier/playbooks/openshift-cluster-seed.yml -e skip_manual_promotion=true -e source_code_url=<YOUR REPO> -e source_code_ref=<YOUR_GIT_REF>`
10. View the Pelorus dashboard to see the metrics for the app.
11. You can continue to make commits to your fork to update the nginx app (for example, make an update to the `index.html` file in `samples/basic-nginx` and push the update to your fork). From there, run `oc start-build basic-nginx-pipeline -n basic-nginx-build` to start the pipeline and see the metrics and app update.
12. You can make updates to the values.yaml file and then run: `helm upgrade pelorus charts/deploy --namespace pelorus`. You should see that the generated secrets (mongodb secret and webhook secret) should not change from the initial installation.
13. Review the Jenkinsfile in `samples/basic-nginx` to see an example of how to send commit information to the webhook from within your own pipeline.
