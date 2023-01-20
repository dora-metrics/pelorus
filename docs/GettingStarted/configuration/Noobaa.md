[NooBaa](https://www.noobaa.io/) is a free, open source option for a software-driven data service that provides S3 object-storage interface. The following is a walkthrough for deploying NooBaa Operator on OpenShift and then configuring Pelorus to consume it as a long term storage solution.

## NooBaa Operator CLI

NooBaa Operator installation may be done using `noobaa` CLI that helps to easy most management tasks. To install it, please refer to the [NooBaa Docs](https://www.noobaa.io/noobaa-operator-cli.html).

>**Note:** It is possible to install `noobaa` CLI inside a Python virtual environment. To do so, change to Pelorus directory (after cloning its repository), and run
>```
>make dev-env
>source .venv/bin/activate
>```

## Deploy NooBaa

To deploy an instance of NooBaa operator, run
```
oc create namespace pelorus
noobaa install --namespace pelorus
```

>**Note:** NooBaa can be deployed in the same namespace as Pelorus or a separate one.

To check that installation was successful, run
```
noobaa status --namespace pelorus
```
by checking the System Status output and ensuring that all the services are marked with ✅.
```
[...]
INFO[0011] System Status:
INFO[0011] ✅ Exists: NooBaa "noobaa"
INFO[0011] ✅ Exists: StatefulSet "noobaa-core"
INFO[0011] ✅ Exists: ConfigMap "noobaa-config"
INFO[0012] ✅ Exists: Service "noobaa-mgmt"
INFO[0012] ✅ Exists: Service "s3"
INFO[0012] ✅ Exists: Service "sts"
INFO[0012] ✅ Exists: Secret "noobaa-db"
INFO[0013] ✅ Exists: ConfigMap "noobaa-postgres-config"
INFO[0013] ✅ Exists: ConfigMap "noobaa-postgres-initdb-sh"
INFO[0013] ✅ Exists: StatefulSet "noobaa-db-pg"
INFO[0014] ✅ Exists: Service "noobaa-db-pg"
INFO[0014] ✅ Exists: Secret "noobaa-server"
INFO[0014] ✅ Exists: Secret "noobaa-operator"
INFO[0014] ✅ Exists: Secret "noobaa-endpoints"
INFO[0015] ✅ Exists: Secret "noobaa-admin"
INFO[0015] ✅ Exists: StorageClass "pelorus.noobaa.io"
INFO[0015] ✅ Exists: BucketClass "noobaa-default-bucket-class"
INFO[0015] ✅ Exists: Deployment "noobaa-endpoint"
INFO[0016] ✅ Exists: HorizontalPodAutoscaler "noobaa-endpoint"
INFO[0016] ✅ (Optional) Exists: BackingStore "noobaa-default-backing-store"
INFO[0016] ✅ (Optional) Exists: CredentialsRequest "noobaa-aws-cloud-creds"
INFO[0016] ⬛ (Optional) Not Found: CredentialsRequest "noobaa-azure-cloud-creds"
INFO[0017] ⬛ (Optional) Not Found: Secret "noobaa-azure-container-creds"
INFO[0017] ⬛ (Optional) Not Found: Secret "noobaa-gcp-bucket-creds"
INFO[0017] ⬛ (Optional) Not Found: CredentialsRequest "noobaa-gcp-cloud-creds"
INFO[0018] ✅ (Optional) Exists: PrometheusRule "noobaa-prometheus-rules"
INFO[0018] ✅ (Optional) Exists: ServiceMonitor "noobaa-mgmt-service-monitor"
INFO[0018] ✅ (Optional) Exists: ServiceMonitor "s3-service-monitor"
INFO[0018] ✅ (Optional) Exists: Route "noobaa-mgmt"
INFO[0019] ✅ (Optional) Exists: Route "s3"
INFO[0019] ✅ (Optional) Exists: Route "sts"
INFO[0019] ✅ Exists: PersistentVolumeClaim "db-noobaa-db-pg-0"
INFO[0019] ✅ System Phase is "Ready"
INFO[0019] ✅ Exists:  "noobaa-admin"

[...]

#----------------#
#- S3 Addresses -#
#----------------#

[...]
InternalDNS : [https://<bucket_access_point>]
[...]

#------------------#
#- S3 Credentials -#
#------------------#

AWS_ACCESS_KEY_ID     : <s3 access key>
AWS_SECRET_ACCESS_KEY : <s3 secret access key>
[...]
```
Also, gather the information needed to configure Pelorus from the command output:

- **S3 Addresses**
    - **InternalDNS**
- **S3 Credentials**
    - **AWS_ACCESS_KEY_ID**
    - **AWS_SECRET_ACCESS_KEY**

To create NooBaa bucket named `<bucket name>`, run
```
noobaa bucket create <bucket name> --namespace pelorus
```

To check if the bucket was created successfully and it is healthy, run
```
noobaa bucket status <bucket name> --namespace pelorus
```

## Pelorus Configuration

With

- `<bucket name>`
- `<bucket_access_point>`
- `<s3 access key>`
- `<s3 secret access key>`

obtained/used in [Deploy NooBaa](#deploy-noobaa), Pelorus configuration is as follows:
```yaml
[...]
thanos_bucket_name: <bucket name>
bucket_access_point: <bucket_access_point>
bucket_access_key: <s3 access key>
bucket_secret_access_key: <s3 secret access key>
[...]
```
