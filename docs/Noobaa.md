# NooBaa and Pelorus Quickstart
NooBaa is a software-driven data service that provides an S3 object-storage interface used for testing and development of the Pelorus project. This section walks through deploying NooBaa Operator on OpenShift and then configuring Pelorus to consume it as a [Long Term Storage](Install.md#configure-long-term-storage-recommended) solution.

## Installing NooBaa Operator CLI
NooBaa Operator is installed using `noobaa` CLI which can be installed by referring to the [NooBaa README](https://github.com/noobaa/noobaa-operator/blob/master/README.md) or as part of the Pelorus dev-env in the Pelorus git folder:

```
make dev-env
source .venv/bin/activate
noobaa --help
```

## Installing NooBaa
To retain Pelorus dashboard data in the long-term, create a namespace, install an instance of [NooBaa operator](https://github.com/noobaa/noobaa-operator) and create a bucket called `thanos`.

**Procedure**

1. Deploy NooBaa in the same namespace as Pelorus or a separate one.

```
oc create namespace pelorus
```
1. Install NooBaa.

```
noobaa install --namespace pelorus
```
1. Store the S3 credentials from installation for updating the Pelorus configuration in a later step.

> **Note:** Credentials can be retrieved using `noobaa status` command:

```
#------------------#
#- S3 Credentials -#
#------------------#

AWS_ACCESS_KEY_ID     : <s3 access key>
AWS_SECRET_ACCESS_KEY : <s3 secred access key>
```
4. Confirm the installation was success by checking the System Status output and verifying all the services are marked with ✅:

```
$ noobaa status
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

5. Create the NooBaa bucket.

> **Note:** Pelorus uses the `thanos` bucket name by default, but users can choose any bucket name.
```
noobaa bucket create thanos
```

6. Verify the bucket was successfully created and running properly.
```
noobaa bucket status thanos
```

## Updating Pelorus Configuration
Follow the steps below to update the Pelorus stack.

1. Follow the instructions provided in the [Long Term Storage](Install.md#configure-long-term-storage-recommended) procedure of the Install Guide.
1. Verify the `<s3 access key>`, `<s3 secred access key>`, and `<bucket name>` from the installation are used, and `s3.noobaa.svc` is used as the bucket access point.
