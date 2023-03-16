# Pelorus Demo

The following will provide instructions to install and configure Pelorus specifically for the use of this demonstration. 
This demonstration will make use of a Tekton pipeline to mimic the development of an application and the subsequent deployments.  This is done to populate Pelorus with data.  The Tekton pipeline pulls source code, builds an example python application in OpenShift and deploys the application.

The details of each build type and the steps required to support Pelorus can be found in the [tekton manifest](./tekton-demo-setup/05-build-and-deploy.yaml)


## Setup Instructions:

* Install the Pelorus operator, using the installation [documentation](../docs/GettingStarted/Installation.md)

* Fork the [dora-metrics/pelorus](https://github.com/dora-metrics/pelorus) git repository to your github organization.

* Add or configure your github-secret with your Github token:
```
oc create secret generic github-secret --from-literal=TOKEN=ghp_<snip> -n pelorus
```  
  * Instructions can be found in the [Authentication to Remote Services](../docs/GettingStarted/configuration/PelorusExporters.md#authentication-to-remote-services) section of the documentation.

## Configure Pelorus:
* Copy the sample Pelorus instance manifest in pelorus/demo/operator_tekton_demo_values.yaml.sample:

```
cp pelorus/demo/tekton-demo-setup/operator_tekton_demo_values.yaml.sample pelorus/demo/tekton-demo-setup/operator_tekton_demo_values.yaml
```

* Edit pelorus/demo/tekton-demo-setup/operator_tekton_demo_values.yaml to match your github organization:
```
sed -i 's/<your_git_org>/weshayutin/' pelorus/demo/tekton-demo-setup/operator_tekton_demo_values.yaml
```

* Apply the Pelorus instance:
```
oc apply -f pelorus/demo/tekton-demo-setup/operator_tekton_demo_values.yaml
```

## Execute
* Execute the demo-tekton.sh command:

```
./demo-tekton.sh -g https://github.com/<your_org/pelorus.git -b binary -r demo_test1
```

* The script can be invoked to automatically commit changes to the source on a development branch and execute in a loop:
```
./demo-tekton.sh -g https://github.com/weshayutin/pelorus.git -b binary -r demo_test2 -c 10 -t 5
```

* To ensure the failure exporter is exercised enable Github issues in your fork.
Open bugs ensuring they are labeled correctly using the [Github issue documentation](../docs/GettingStarted/QuickstartTutorial.md#github-issues).  

  * Two labels are required:
     * label: bug
     * label: production_issue/name=basic-python-tekton
  * Open and close bugs as needed.

## Help and Support
Help:
```
./demo-tekton.sh -h
```


|Build Type   |Status         |Notes                                                |
|:------------|:--------------|:----------------------------------------------------|
| binary      | supported     | requires exporter committime-exporter               |
| buildConfig | supported     | requires exporter committime-exporter               |
| s2i         | supported     | requires exporter committime-image-exporter with provider=image    |   


