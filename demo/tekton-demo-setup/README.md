# tekton-demo-setup

This contains OpenShift resources to set up a Tekton Python demo for use with Pelorus.
Compatible with OpenShift 4.20+ and Tekton Pipelines v1 API.

## Prerequisites

- OpenShift 4.20+ cluster with cluster-admin access
- OpenShift Pipelines operator installed (see `02-tekton-operator.yaml`)
- `oc` CLI authenticated to the cluster

## Setup Steps

1. **Create the project namespace:**

   ```bash
   oc process -f 01-new-project-request_template.yaml -p PROJECT_NAME=basic-python-tekton | oc apply -f -
   ```

2. **Install the OpenShift Pipelines operator** (if not already installed):

   ```bash
   oc apply -f 02-tekton-operator.yaml
   ```

3. **Create the pipeline RBAC role:**

   ```bash
   oc apply -f 03-rbac-pipeline-role.yaml
   ```

4. **Bind the pipeline service account:**

   ```bash
   oc process -f 04-service-account_template.yaml -p PROJECT_NAMESPACE=basic-python-tekton | oc apply -f -
   ```

5. **Deploy the build and application resources:**

   ```bash
   oc process -f 05-build-and-deploy.yaml | oc apply -f -
   ```

6. **Run the pipeline:**

   ```bash
   oc create -f - <<EOF
   apiVersion: tekton.dev/v1
   kind: PipelineRun
   metadata:
     generateName: basic-python-tekton-pipeline-run-
     namespace: basic-python-tekton
   spec:
     pipelineRef:
       name: basic-python-tekton-pipeline
     workspaces:
       - name: repo
         persistentVolumeClaim:
           claimName: basic-python-tekton-build-pvc
   EOF
   ```

## Pelorus Configuration

See `operator_tekton_demo_values.yaml.sample` for a sample Pelorus operator configuration
that works with this demo. Copy it and adjust the values (especially secrets and
git organization) for your environment.

## Key Changes for OpenShift 4.20+

- Uses Tekton Pipelines API `tekton.dev/v1` (v1beta1 is removed)
- Uses `Deployment` (apps/v1) instead of `DeploymentConfig` (removed in OCP 4.20)
- Uses `python-312` base image instead of `python-39`
- Task references use `kind: Task` (default) instead of `kind: ClusterTask` (removed)
- Task results include explicit `type: string` as required by v1 API
