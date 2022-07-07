# Pelorus Demo

### Assumptions
- oc, helm command line tools installed
- Logged into OCP Cluster via the CLI and UI as kubeadmin

### Goal

In this demo, you will get a taste of how Pelorus captures a change going through the application's delivery cycle.

* Install and configure Pelorus
* Install a sample application that Pelorus will measure
* Set a baseline of data for Pelorus measurements
* Create a new commits, and Github issues
* Watch as the metrics and trends change as new versions roll out

Understand that Pelorus should be used as a conversation tool to read the trends in metrics and react by making informed investments in the software delivery process.

--------------------------

# Lead Time for Change and Deployment Frequency

![dora_lead_deployment](img/dora_metrics1.png)

> **Note:** More information about the four key DORA metrics can be found at the [Software Delivery Performance section](Dashboards.md) 

## Workflow - Install
- install and configure Pelorus
- install a sample application

### Pelorus developer environment

This is an **optional step** for developers that will setup a Python
virtual environment and install prerequisite python and openshift cli tools and libraries.

        cd pelorus
        make dev-env
        source .venv/bin/activate
        make help

### Pelorus install steps

* Create the pelorus namespace

        oc create namespace pelorus

* Install the required granfa and prometheus operators

        helm install operators charts/operators --namespace pelorus

* Wait for the operator install to complete

        $ oc get pods -n pelorus
        NAME                                                   READY     STATUS    RESTARTS   AGE
        grafana-operator-controller-manager-7678cc5c7c-spvls   2/2       Running   0          22s
        prometheus-operator-559d659944-fvsjg                   1/1       Running   0          10s
    
* Install Pelorus
    
        helm install pelorus charts/pelorus --namespace pelorus

* Wait for the Pelorus install to complete

        $ oc get pods -n pelorus
        NAME                                                   READY     STATUS      RESTARTS      AGE
        deploytime-exporter-1-deploy                           0/1       Completed   0             93s
        deploytime-exporter-1-rwk5l                            1/1       Running     0             90s
        grafana-deployment-55f77ccc8f-d7m92                    2/2       Running     0             84s
        grafana-operator-controller-manager-7678cc5c7c-spvls   2/2       Running     0             4m5s
        prometheus-operator-559d659944-fvsjg                   1/1       Running     0             3m53s
        prometheus-prometheus-pelorus-0                        3/3       Running     1 (89s ago)   93s
        prometheus-prometheus-pelorus-1                        3/3       Running     1 (89s ago)   93s

* Finally check the install

        oc get all -n pelorus
    

### Pelorus configuration

* Make a copy of [the values.yaml file in the pelorus repo](https://github.com/konveyor/pelorus/blob/master/charts/pelorus/values.yaml) ([raw link for curl-ing](https://raw.githubusercontent.com/konveyor/pelorus/master/charts/pelorus/values.yaml)) and save it to /var/tmp/values.yaml

        cp charts/pelorus/values.yaml /var/tmp/

* Update the "exporters" section of the /var/tmp/values.yaml to match the following example:

        exporters:
          instances:
          - app_name: deploytime-exporter
            exporter_type: deploytime
            extraEnv:
            - name: LOG_LEVEL
              value: DEBUG
            - name: NAMESPACES
              value: mongo-persistent
          - app_name: committime-exporter
            exporter_type: committime
            extraEnv:
            - name: LOG_LEVEL
              value: DEBUG
            - name: NAMESPACES
              value: mongo-persistent

>**Note:** [Documentation regarding values.yaml can be found on our readthedocs page.](https://pelorus.readthedocs.io/en/latest/Configuration/)

* Apply the updated values for Pelorus by executing:

        helm upgrade pelorus charts/pelorus --namespace pelorus --values /var/tmp/values.yaml

> **Note:** Please pause to allow the committime exporter pod to be deployed.

Pelorus should now be installed and configured to measure the todolist sample app. We'll have to deploy the sample application to view measurements from Pelorus's Grafana dashboard.

## Todolist sample application install steps

* git clone the forked copy of konveyor/mig-demo-apps

        git clone https://github.com/your_org/mig-demo-apps.git

* Install the todolist-mongo-go sample application

        cd mig-demo-apps/apps/todolist-mongo-go
        export GITHUB_ORG=<YOUR_REAL_GITHUB_FORK_ORG>
        sed -i.original "s/your_org/${GITHUB_ORG}/g" mongo-persistent.yaml
        oc create -f mongo-persistent.yaml
    

The todolist application and mongo database should now build and deploy into the mongo-persistent namespace.

* Check the build

        oc get all -n mongo-persistent

>***Note:*** Please pause to allow the todolist pod to build and deploy.

*  Ensure that your github fork of mig-demo-apps is correctly set as the uri value in the todolist BuildConfig.
    
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
    
## View the Pelorus measurements

* In your OpenShift Pelorus project page, open the link to granafa or get the link via the cli:

        oc get route grafana-route -o=go-template='https://{{.spec.host | printf "%s\n" }}'

* Navigate to **"pelorus / Software Delivery Performance - By App"**
* Select the **todolist** application

You should now see at least one measurement for "Lead time for Change" and "Deployment Frequency"

![gnome-shell-screenshot-3zh4l2](img/initial_measurement.png)


## WorkFlow - Updates to your application's source code 
- Make changes to the application, e.g. replace a line to index.html
- commit changes to source control
- Watch the application redeploy with the changes to be captured by Pelorus

## Github Webhook

One can more easily watch how Pelorus works by automatically building and deploying the todolist app when a commit is pushed to Github by utizing Github's webhooks.

* To get the build webhook URL you can navigate to the todolist BuildConfig details or via the cli:

        oc describe buildconfig.build.openshift.io/todolist -n mongo-persistent
    
> **Note:**
> The secret is hardcoded in the todolist manifest template to be:
  `4Xwu0tyAab90aaoasd88qweAasdaqvjknfrl3qwpo`
        

* Navigate to https://github.com/your_org/mig-demo-apps/settings/hooks
* Paste the URL with the real secret replacing the text <secret>
* Toggle SSL as needed, for testing consider disabling.
* Content type: application/json
* Click, "Add webhook"

## Update the application source
The following screenshot is the original todolist application prior to a change

![todolist](img/todolist_orig.png)

* The text "Enter an activity" does not seem clear, let's change that to "Add a todo"

        cd mig-demo-apps/apps/todolist-mongo-go
        sed -i.bak 's/Enter an activity../Add a todo../g' index.html
    
* If you are happy with the change, commit and push

        git add .
        git commit -m "update text box"
        git push origin master
    

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

* **Lead Time for Change:**
    * Lead Time = {deploy time} - {commit time}

    * The lead time for change should initially go down as we just pushed a commit.  The time difference between changes to the original git repository and your personal forked repo will most likely cause this metric to go down.

* **Deployment Frequency:**
    * Deployment Frequency = {number of deploys in a defined time frame}

    * There have been two deployments since this demonstration was started, the initial deployment and now the redeployment after pushing a change to the git repository.  The deployment frequency should have gone up by 100% in the last 15 minutes.  Once your initial deployment time is longer than 15 minutes in the past, you will find your interval has fallen by 50%.

### See the raw data in the Pelorus Exporter logs
Check the Pelorus committime output for the commit hash that was pushed:

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


# Mean Time to Restore and Change Failure Rate

![dora_fail_recover](img/dora_metrics2.png)

> **Note:** More information about the four key DORA metrics can be found at the [Software Delivery Performance section](Dashboards.md) 

### Assumptions
- Github issues are enabled in https://github.com/your_org/mig-demo-apps/settings

### Workflow - Failure and Resolution
- Create and resolve bugs in Github issues that exercise Pelorus metrics
- View the changes to the `Mean Time to Restore` and `Change Failure Rate` metrics.


### Pelorus configuration

>**Note:**
> * A users [Github personal access token](https://github.com/settings/tokens) is required
> * The `PROJECTS` key's value is the fork of the mig-apps-demo repository.

* Update the "exporters" section of the /var/tmp/values.yaml to match the following example:

        exporters:
          instances:
          - app_name: deploytime-exporter
            exporter_type: deploytime
            extraEnv:
            - name: LOG_LEVEL
              value: DEBUG
            - name: NAMESPACES
              value: mongo-persistent
          - app_name: committime-exporter
            exporter_type: committime
            extraEnv:
            - name: LOG_LEVEL
              value: DEBUG
            - name: NAMESPACES
              value: mongo-persistent
          - app_name: failure-exporter
            exporter_type: failure
            extraEnv:
            - name: LOG_LEVEL
              value: DEBUG
            - name: PROVIDER
              value: github
            - name: TOKEN
              value: ghp_J<snip>
            - name: PROJECTS
              value: <your_org>/mig-demo-apps

* Documentation regarding values.yaml can be found [in the configuration section.](Configuration.md)
  Apply the updated values for Pelorus by executing:

    
        helm upgrade pelorus charts/pelorus --namespace pelorus --values /var/tmp/values.yaml
    

>**Note:** Please pause to allow the failure exporter pod to build and deploy.

* Check the output from the failure exporter.  No bugs should be found at this time.

    
        curl $(oc get route -n pelorus failure-exporter -o=template='http://{{.spec.host | printf "%s\n"}}')
    

### Github Issues

Pelorus will utilize two tags to determine if a Github issue is associated with the todolist-mongo application.  We'll need the default `bug` tag. Additionally, by default Pelorus requires that all issues associated with a particular application be labeled with the app.kubernetes.io/name=<app_name> label. This works the same way as the deployment configuration.

* Navigate to https://github.com/your_org/mig-demo-apps/issues
  * Required Github issue tags:
    * `bug`
    * `app.kubernetes.io/name=todolist`

![github_start](img/github_issues_setup.png)


### Create a Github issues

Now we will create an issue in Github and set the appropriate labels.
Pelorus will register an issue as a deployment failure only if it is labeled as a `bug` and labeled with the application name `app.kubernetes.io/name=todolist`

* Create a Github issue and label it appropriately to register a failure.

![github_issue1](img/github_issue_1.png)

* Now refresh the Grafana dashboard and you should see the Change Failure Rate go up.

![change_failure_rate_1](img/change_failure_rate_1.png)

* Let's now create a non critical bug. A bug that does not indicate a deployment failure in your todolist application.  A the bug label however do *not* add the application label

![issue_untagged](img/issue_2_non_deployment.png)

* Ensure that issue #2 is not impacting our failure rate metric by curl-ing the output of the failure exporter.

  **command:**

    curl $(oc get route -n pelorus failure-exporter -o=template='http://{{.spec.host | printf "%s\n"}}')

*  Issue #1 should be found in the output of the curl.  Issue #2 will not be registered as a deployment failure because the issue is *not* tagged with `app.kubernetes.io/name=todolist`

Notice the message `failure_creation_timestamp`.  This indicates the time the issue was created.

  **output:**

    failure_creation_timestamp{app="todolist",issue_number="1"} *654704543e+09
    

* Now lets resolve issue #1 and see how that impacts our `Failure Rate` and the `Mean Time to Restore`

![issue_close](img/github_issue_1_close.png)

* Check the output from the failure exporter again and we should see a `failure_resolution_timestamp`, which indicates when a bug was closed.

  **command:**

      curl $(oc get route -n pelorus failure-exporter -o=template='http://{{.spec.host | printf "%s\n"}}')

  **output:**

      failure_creation_timestamp{app="todolist",issue_number="1"} *654704543e+09
      failure_resolution_timestamp{app="todolist",issue_number="1"} *654705784e+09

* Now we should also data in the `Mean Time to Restore` metric in Grafana

![mean_time_to_restore](img/mean_time_to_restore.png)

* **Mean Time to Restore:**
    * Mean Time to Restore = Average( {failure_resolution_timestamp} - {failure_creation_timestamp} )

    * How long it takes to restore service when a service incident occurs.

* **Change Failure Rate:**
    * Change Failure Rate = {number of failed changes} / {total number of changes to the system}

    * A key quality metric that measures what percentage of changes to production fail.  It is crucial to have alignment on what constitutes a failure.  The recommended definition is a change that either results in degraded service or subsequently requires remediation.


## Parially Automated Demo

> **Note:**
  > Before starting please ensure pelorus has been uninstalled completely. The automated demo scripts expect that Pelorus is not installed and the Pelorus namespace is *not* present.

The Pelorus and todolist application can be installed automatically.  Using the forked copy of [mig-demo-apps](https://github.com/konveyor/mig-demo-apps) referenced as `https://github.com/<your_org>/mig-demo-apps`, execute the following steps:


* Setup the github webhook prior to execution

    * The Github webhook address should be:

        ```
        https://api.cluster-<snip>.com:6443/apis/build.openshift.io/v1/namespaces/mongo-persistent/buildconfigs/todolist/webhooks/4Xwu0tyAab90aaoasd88qweAasdaqvjknfrl3qwpo/github
        ```

* Enable Github Issues in the repository's settings prior to execution

    * In order for the demo to fully succeed at least one Github issue must be present with the `bug` and `app.kubernetes.io/name=todolist` issue labels.

* Execute `run-pelorus-e2e-tests`
  
        cd pelorus
        export KUBECONFIG=$PATH_TO_KUBECONFIG_FILE
        export TOKEN=<github_personal_access_token>
        make dev-env
        source .venv/bin/activate
        scripts/run-pelorus-e2e-tests -o <your_org> -e failure

> **Note:**  Please wait as Pelorus is installed and the todolist application are deployed.

* Create a source code change to the todolist app and git push

*  If the Github webhook is enabled, wait for the rebuild or trigger the build manually in OpenShift.

*  Repeat with additional git commits

* Create and close Github issues while ensuring the appropriate issue labels are set.  