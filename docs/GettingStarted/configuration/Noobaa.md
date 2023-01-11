# NooBaa and Pelorus Quickstart

NooBaa is a software-driven data service that provides S3 object-storage interface that we use for testing and development of Pelorus project.

The following is a walkthrough for deploying NooBaa Operator on OpenShift and then configuring Pelorus to consume it as a [Long Term Storage](../ProductionBestPractice/#configure-long-term-storage-recommended) solution.

## Install NooBaa Operator CLI

NooBaa Operator installation may be done using `noobaa` CLI that helps to easy most management tasks.

To install `noobaa` CLI please refer to the [NooBaa README](https://github.com/noobaa/noobaa-operator/blob/master/README.md) or simply install it as part of our dev-env from the pelorus git folder:

```
make dev-env
source .venv/bin/activate
noobaa --help
```

## Configure Namespace

NooBaa can be deployed in the same namespace as Pelorus or a separate one.

```
oc create namespace pelorus
```

## Install NooBaa

To retain Pelorus dashboard data in the long-term, we'll deploy an instance of [NooBaa operator](https://github.com/noobaa/noobaa-operator) and create a bucket called `thanos`.

### Deploy NooBaa

To deploy NooBaa simply run:

```
noobaa install --namespace pelorus
```

At this stage it's important to store S3 Credentials, that they appeared during `noobaa install --namespace pelorus` step.
They will be used later in the [Update Pelorus Configuration](#update-pelorus-configuration) step. Credentials can be always received using `noobaa status` command:

```
#------------------#
#- S3 Credentials -#
#------------------#

AWS_ACCESS_KEY_ID     : <s3 access key>
AWS_SECRET_ACCESS_KEY : <s3 secret access key>
```

After running `noobaa install --namespace pelorus` step, you may confirm that installation went fine by checking the System Status output and ensuring that ll the services are marked with ✅:

```
$ noobaa status --namespace pelorus
[...]
INFO[0004] System Status:
INFO[0004] ✅ Exists: NooBaa "noobaa"
INFO[0004] ✅ Exists: StatefulSet "noobaa-core"
INFO[0004] ✅ Exists: ConfigMap "noobaa-config"
INFO[0004] ✅ Exists: Service "noobaa-mgmt"
INFO[0005] ✅ Exists: Service "s3"
INFO[0005] ✅ Exists: Secret "noobaa-db"
INFO[0005] ✅ Exists: ConfigMap "noobaa-postgres-config"
INFO[0005] ✅ Exists: ConfigMap "noobaa-postgres-initdb-sh"
INFO[0005] ✅ Exists: StatefulSet "noobaa-db-pg"
INFO[0005] ✅ Exists: Service "noobaa-db-pg"
INFO[0005] ✅ Exists: Secret "noobaa-server"
INFO[0005] ✅ Exists: Secret "noobaa-operator"
INFO[0005] ✅ Exists: Secret "noobaa-endpoints"
INFO[0005] ✅ Exists: Secret "noobaa-admin"
INFO[0005] ✅ Exists: StorageClass "noobaa.noobaa.io"
INFO[0005] ✅ Exists: BucketClass "noobaa-default-bucket-class"
INFO[0005] ✅ Exists: Deployment "noobaa-endpoint"
INFO[0006] ✅ Exists: HorizontalPodAutoscaler "noobaa-endpoint"
INFO[0006] ✅ (Optional) Exists: BackingStore "noobaa-default-backing-store"
INFO[0006] ✅ (Optional) Exists: CredentialsRequest "noobaa-aws-cloud-creds"
INFO[0006] ⬛ (Optional) Not Found: CredentialsRequest "noobaa-azure-cloud-creds"
INFO[0006] ⬛ (Optional) Not Found: Secret "noobaa-azure-container-creds"
INFO[0006] ⬛ (Optional) Not Found: Secret "noobaa-gcp-bucket-creds"
INFO[0006] ⬛ (Optional) Not Found: CredentialsRequest "noobaa-gcp-cloud-creds"
INFO[0006] ✅ (Optional) Exists: PrometheusRule "noobaa-prometheus-rules"
INFO[0006] ✅ (Optional) Exists: ServiceMonitor "noobaa-mgmt-service-monitor"
INFO[0006] ✅ (Optional) Exists: ServiceMonitor "s3-service-monitor"
INFO[0006] ✅ (Optional) Exists: Route "noobaa-mgmt"
INFO[0006] ✅ (Optional) Exists: Route "s3"
INFO[0007] ✅ Exists: PersistentVolumeClaim "db-noobaa-db-pg-0"
INFO[0007] ✅ System Phase is "Ready"
INFO[0007] ✅ Exists:  "noobaa-admin"
```

### Create NooBaa bucket

We use default `thanos` bucket name. User may choose any bucket name.
To create `thanos` NooBaa bucket:

```
noobaa bucket create thanos --namespace pelorus
```

At any time to check if the bucket was created successfully and it's healthy run the command:

```
noobaa bucket status thanos --namespace pelorus
```

## Update Pelorus Configuration

To update our Pelorus stack, follow the instructions provided in the [Long Term Storage](../ProductionBestPractice/#configure-long-term-storage-recommended).

Ensure that `<s3 access key>`, `<s3 secret access key>` and the `<bucket name>` are used from the [Deploy NooBaa
](#deploy-noobaa) step and `s3.pelorus.svc:443`, which is an `S3 InternalDNS Address` from the `noobaa status --namespace pelorus` command, as bucket access point as in example:

```yaml
# Thanos / S3 Storage with noobaa
thanos_bucket_name: thanos
bucket_access_point: s3.pelorus.svc:443
bucket_access_key: <s3 access key>
bucket_secret_access_key: <s3 secred access key>

exporters:
  instances:
  - app_name: committime-exporter
    exporter_type: committime
    env_from_secrets:
    - github-secret
    env_from_configmaps:
    - pelorus-config
    - committime-config
```
