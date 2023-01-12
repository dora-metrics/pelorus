# demo

Scripts to demonstrate pelorus functionality live here.

## demo-tekton.sh

The following will provide a Tekton pipeline that can build an example python application in various ways. The tasks additionally provide the required metadata for Pelorus and launch and test the sample application.

The details of each build type and the steps required to support Pelorus can be found in the [tekton manifest](./tekton-demo-setup/03-build-and-deploy.yaml)


Instructions:

* Fork the konveyor/pelorus git repository to your github organization.

* Add or configure your github-secret with your Github token
```
oc create secret generic github-secret --from-literal=TOKEN=ghp_<snip> -n pelorus
```

* Copy the sample Pelorus instance manifest in pelorus/demo/operator_tekton_demo_values.yaml.sample

```
cp pelorus/demo/tekton-demo-setup/operator_tekton_demo_values.yaml.sample pelorus/demo/tekton-demo-setup/operator_tekton_demo_values.yaml
```

* Edit pelorus/demo/tekton-demo-setup/operator_tekton_demo_values.yaml to match your github organization

* Apply the Pelorus instance
```
oc apply -f pelorus/demo/tekton-demo-setup/operator_tekton_demo_values.yaml
```



* Execute the demo-tekton.sh command:

```
./demo-tekton.sh -g https://github.com/<your_org/pelorus.git -b binary -r demo_test1
```

Help:
```
./demo-tekton.sh -h
```


|Build Type   |Status         |Notes                                                |
|:------------|:--------------|:----------------------------------------------------|
| binary      | supported     | requires exporter committime-exporter               |
| buildConfig | supported     | requires exporter committime-exporter               |
| s2i         | supported     | requires exporter committime-image-exporter with provider=image    |   


