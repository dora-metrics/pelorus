# demo

Scripts to demonstrate pelorus functionality live here.

## demo-tekton.sh

The following will provide a Tekton pipeline that can build an example python application in various ways. The tasks additionally provide the required metadata for Pelorus and launch and test the sample application.

The details of each build type and the steps required to support Pelorus can be found in the [tekton manifest](./tekton-demo-setup/03-build-and-deploy.yaml)

Example:
```
./demo-tekton.sh -g https://github.com/konveyor/pelorus.git -b binary
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


An example values.yaml file that can be used as a template with the demo-tekton.sh
script in the tekton-demo-setup directory.

## demo.sh

See the [demo docs in the official pelorus documentation.](https://pelorus.readthedocs.io/en/latest/Demo/)
