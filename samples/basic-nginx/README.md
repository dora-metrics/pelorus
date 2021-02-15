# A Sample OpenShift Pipeline for a Nginx Application - Generic CommitTime Exporter with Build Webhook

This example demonstrates how to implement a full end-to-end Jenkins Pipeline for a static application in OpenShift Container Platform. It assumes that the build webhook and generic committime exporter are deployed in the pelorus namespace.

This sample demonstrates the following capabilities:

* Deploying an integrated Jenkins server inside of OpenShift
* Running both custom and oob Jenkins slaves as pods in OpenShift
* "One Click" instantiation of a Jenkins Pipeline using OpenShift's Jenkins Pipeline Strategy feature
* Building a Jenkins pipeline with library functions from our [pipeline-library](https://github.com/redhat-cop/pipeline-library)
* Automated rollout using the [openshift-appler](https://github.com/redhat-cop/openshift-applier) project.

## Automated Deployment

This quickstart can be deployed quickly using Ansible. Here are the steps.

1. Clone [this repo](https://github.com/redhat-cop/container-pipelines)
2. `cd container-pipelines/basic-nginx`
3. Run `ansible-galaxy install -r requirements.yml --roles-path=galaxy`
4. Log into an OpenShift cluster, then run the following command.
```
$ ansible-playbook -i ./.applier/ galaxy/openshift-applier/playbooks/openshift-cluster-seed.yml
```

At this point you should have 4 projects created (`basic-nginx-build`, `basic-nginx-dev`, `basic-nginx-stage`, and `basic-nginx-prod`) with a pipeline in the `-build` project, and our [Nginx](../basic-nginx) demo app deployed to the dev/stage/prod projects.

## Architecture

The following breaks down the architecture of the pipeline deployed, as well as walks through the manual deployment steps

### OpenShift Templates

The components of this pipeline are divided into two templates.

The first template, `.openshift/templates/build.yml` is what we are calling the "Build" template. It contains:

* A `jenkinsPipelineStrategy` BuildConfig
* An `s2i` BuildConfig
* An ImageStream for the s2i build config to push to

The build template contains a default source code repo for a java application compatible with this pipelines architecture (https://github.com/redhat-cop/spring-rest).

The second template, `.openshift/deployment/template.yml` is the "Deploy" template. It contains:

* A nginx DeploymentConfig
* A Service definition
* A Route
* An Image Stream definition
* A Role Binding definition

The idea behind the split between the templates is that I can deploy the build template only once (to my build project) and that the pipeline will promote my image through all of the various stages of my application's lifecycle. The deployment template gets deployed once to each of the stages of the application lifecycle (once per OpenShift project).

### Pipeline Script

This project includes a sample `Jenkinsfile` pipeline script that could be included with a Nginx project in order to implement a basic CI/CD pipeline for that project, under the following assumptions:

* The project is built with Maven
* The OpenShift projects that represent the Application's lifecycle stages are of the naming format: `<app-name>-dev`, `<app-name>-stage`, `<app-name>-prod`.

This pipeline defaults to use our [Nginx Demo App](../basic-nginx).

## Bill of Materials

* One or Two OpenShift Container Platform Clusters
  * OpenShift 3.7+ is required
  * [Red Hat Nginx 1.12](https://access.redhat.com/containers/?tab=overview&get-method=unauthenticated#/registry.access.redhat.com/rhscl/nginx-112-rhel7) image is required
* Access to GitHub

## Manual Deployment Instructions

### 1. Create Lifecycle Stages

For the purposes of this demo, we are going to create three stages for our application to be promoted through.

- `basic-nginx-build`
- `basic-nginx-dev`
- `basic-nginx-stage`
- `basic-nginx-prod`

In the spirit of _Infrastructure as Code_ we have a YAML file that defines the `ProjectRequests` for us. This is as an alternative to running `oc new-project`, but will yeild the same result.

```
$ oc create -f .openshift/projects/projects.yml
projectrequest "basic-nginx-build" created
projectrequest "basic-nginx-dev" created
projectrequest "basic-nginx-stage" created
projectrequest "basic-nginx-prod" created
```

### 2. Stand up Jenkins master in dev

For this step, the OpenShift default template set provides exactly what we need to get jenkins up and running.

```
$ oc process openshift//jenkins-ephemeral | oc apply -f- -n basic-nginx-build
route "jenkins" created
deploymentconfig "jenkins" created
serviceaccount "jenkins" created
rolebinding "jenkins_edit" created
service "jenkins-jnlp" created
service "jenkins" created
```

### 4. Instantiate Pipeline

A _deploy template_ is provided at `.openshift/deployment/template.yml` that defines all of the resources required to run our Tomcat application. It includes:

* A `Service`
* A `Route`
* An `ImageStream`
* A `DeploymentConfig`
* A `RoleBinding` to allow Jenkins to deploy in each namespace.

This template should be instantiated once in each of the namespaces that our app will be deployed to. For this purpose, we have created a param file to be fed to `oc process` to customize the template for each environment.

Deploy the deployment template to all three projects.
```
$ oc process -f .openshift/deployment/template.yml -p=APPLICATION_NAME=basic-nginx
 -p NAMESPACE=basic-nginx-dev -p=SA_NAMESPACE=basic-nginx-build -p | oc apply -f-

$ oc process -f .openshift/deployment/template.yml -p=APPLICATION_NAME=basic-nginx
 -p NAMESPACE=basic-nginx-stage -p=SA_NAMESPACE=basic-nginx-build -p | oc apply -f- | oc apply -f-

$ oc process -f .openshift/deployment/template.yml -p=APPLICATION_NAME=basic-nginxs
 -p NAMESPACE=basic-nginx-prod -p=SA_NAMESPACE=basic-nginx-build -p | oc apply -f-
```

A _build template_ is provided at `.openshift/builds/template.yml` that defines all the resources required to build our nginx app. It includes:

* A `BuildConfig` that defines a `JenkinsPipelineStrategy` build, which will be used to define out pipeline.
* A `BuildConfig` that defines a `Source` build with `Binary` input. This will build our image.

Deploy the pipeline template in build only.
```
$ oc process -f applier/templates/build.yml -p=APPLICATION_NAME=basic-nginx
 -p NAMESPACE=basic-nginx-dev -p=SOURCE_REPOSITORY_URL="https://github.com/redhat-cop/container-pipelines.git" | oc apply -f-
```

At this point you should be able to go to the Web Console and follow the pipeline by clicking in your `basic-nginx-build` project, and going to *Builds* -> *Pipelines*. At several points you will be prompted for input on the pipeline. You can interact with it by clicking on the _input required_ link, which takes you to Jenkins, where you can click the *Proceed* button. By the time you get through the end of the pipeline you should be able to visit the Route for your app deployed to the `myapp-prod` project to confirm that your image has been promoted through all stages.

## Cleanup

Cleaning up this example is as simple as deleting the projects we created at the beginning.

```
oc delete project basic-nginx-build basic-nginx-dev basic-nginx-prod basic-nginx-stage
```
