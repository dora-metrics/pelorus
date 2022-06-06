# Pelorus Demo
## Lead Time for Change and Deployment Frequency

![dora_lead_deployment](img/dora_metrics.png)


### Assumptions
- oc command line tools installed
- Logged into OCP Cluster via the CLI and UI as kubeadmin

### Goal

In this demo, you will get a taste of how Pelorus captures a change going through the application's delivery cycle.

1. Initializing Pelorus sets the baseline by looking at existing stored data
2. Create a new commit
3. Watch as the metrics and trends change as new versions roll out

Pelorus should be used as a conversation tool to read the trends in metrics and react by making informed investments in the software delivery process.

## Prerequisites

* Pelorus is installed and running
  * Follow the steps outlined in the [todolist install guide](../samples/todolist.md#pelorus-install-steps)

* The todolist sample application is installed and running
  * Follow the steps outlined [todolist sample install guide](../samples/todolist.md#todolist-sample-application-install-steps)

> **Note:**
> Ensure that your github fork of mig-demo-apps is correctly set as the uri value in the todolist BuildConfig.
```
- kind: BuildConfig
  apiVersion: build.openshift.io/v1
  metadata:
    name: todolist
<snip>
      source:
        type: Git
        git:
          uri: https://github.com/weshayutin/mig-demo-apps.git
          ref: master

```

## Flow
- Make changes to the application, e.g. replace a line to index.html
- commit changes to source control
- Watch the application redeploy with the changes to be captured by Pelorus

## Github Webhook

One can more easily watch how Pelorus works by automatically building and deploying the todolist app when a commit is pushed to Github by utizing Github's webhooks.

1. To get the build webhook URL you can navigate to the todolist BuildConfig details or via the cli:
```
oc get all -n mongo-persistent
oc describe buildconfig.build.openshift.io/todolist -n mongo-persistent
```
> **Note:**
> The secret is hardcoded in the todolist manifest template to be:
```
4Xwu0tyAab90aaoasd88qweAasdaqvjknfrl3qwpo
```
* Navigate to https://github.com/your_org/mig-demo-apps/settings/hooks
* Paste the URL with the real secret replacing the text <secret>
* Toggle SSL as needed, for testing consider disabling.
* Content type: application/json
* Click, "Add webhook"

## Update the application source
The following screenshot is the original todolist application prior to a change

![todolist](img/todolist_orig.png)

* The text "Enter an activity" does not seem clear, let's change that to "Add a todo"

```
cd mig-demo-apps/apps/todolist-mongo-go
sed -i.bak 's/Enter an activity../Add a todo../g' index.html
```

* If you are happy with the change, commit and push
```
git add .
git commit -m "update text box"
git push origin master
```

### Rebuilding and Deploying the todolist application
* Once the commit is pushed the application will automatically rebuild because we have setup the github webhook.

* You will now see the todolist application start to rebuild

![todolist_rebuild](img/todolist_rebuild.png)

### Understand the changes to the Grafana Dashboard

> **Note:**
> The dashboard is avaiable by navigating to grafana via the url found with:<br />
> `oc -n pelorus get route grafana-route -o json | jq -r '.spec.host'`<br />
> And navigating Home(top left) -> pelorus -> Softare Delivery Performance

* Navigate to the Granfa Dashboard, Software Delivery Performance by App, set the interval to 15 minutes.
Pelorus will now read the updated commit and register a new deploytime.  You should now see a total for two deployments.

![First-Update](img/todolist_update1.png)

* Lead Time for Change:
  * Lead Time = {deploy time} - {commit time}

  * The lead time for change should initially go down as we just pushed a commit.  The time difference between changes to the original git repository and your personal forked repo will most likely cause this metric to go down.

* Deployment Frequency:
  * Deployment Frequency = {number of deploys in a defined time frame}

  * There have been two deployments since this demonstration was started, the initial deployment and now the redeployment after pushing a change to the git repository.  The deployment frequency should have gone up by 100% in the last 15 minutes.  Once your initial deployment time is longer than 15 minutes in the past, you will find your interval has fallen by 50%.

### See the raw data in the Pelorus Exporter logs
Check the Pelorus committime output for the commit hash that was pushed

```
git log -p -1
```
Compare the output with the following command:
```
curl $(oc get route -n pelorus committime-exporter -o=template='http://{{.spec.host | printf "%s\n"}}')
```

Also notice the built deployed image sha is visible via the deploytime-exporter

```
curl $(oc get route -n pelorus deploytime-exporter -o=template='http://{{.spec.host | printf "%s\n"}}')
```

### See the change to your todolist application
You can now also check on your todolist application and see the updated text change "Add a todo"
![todolist-fixed](img/todolist_fixed.png)


## Troubleshooting

If exporters are not functioning or deployed, no data will show up in the dashboard. It will look like the following:
![No-Data](img/pelorus-dashboard-no-data.png)

* Please check the logs of exporter pod.

An "idle" state could resemble:
![Idle-Data](img/pelorus-dashboard-idle-data.png)


## Automated Demo

The Pelorus and todolist application can be installed automatically.  Using the forked copy of [mig-demo-apps](https://github.com/konveyor/mig-demo-apps) referenced as `https://github.com/<your_org>/mig-demo-apps`, execute the following steps:

> **Note:**
> The automated demo expects that Pelorus is not installed and the Pelorus namespace is *not* present.

1. Setup the github webhook prior to execution

2. Execute `run-pelorus-e2e-tests`
```
# ensure pelorus has been uninstalled completely
cd pelorus
export KUBECONFIG=$PATH_TO_KUBECONFIG_FILE
make dev-env
source .venv/bin/activate
scripts/run-pelorus-e2e-tests -o <your_org>
```

3. Create a change to the todolist app
For example:
```
cd mig-demo-apps/apps/todolist-mongo-go
sed -i.bak 's/Enter an activity../Add a todo../g' index.html
git add .
git commit -m "update text box"
git push origin main
```

4. If the Github webhook is enabled, wait for the rebuild or trigger the build manually in OpenShift.

5. Repeat with additional git commits
