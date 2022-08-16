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

|Build Type   |Status         |
|:------------|:--------------|
| binary      | supported     |
| buildConfig | supported     | 
| s2i         | [work in progress](https://github.com/konveyor/pelorus/issues/371)|

## demo.sh

See the [demo docs in the official pelorus documentation.](https://pelorus.readthedocs.io/en/latest/Demo/)
