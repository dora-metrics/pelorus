# MinIO and Pelorus Quickstart

The following is a walkthrough for deploying MinIO on OpenShift and then configuring Pelorus to consume it as a [Long Term Storage](Install.md#configure-long-term-storage-recommended) solution.

## Configure Namespace and Storage Security

To allow minio to run, add a security constraint context. Run the following command from within the root repository directory

```
oc create namespace minio
oc apply -f storage/minio-scc.yaml
```

## Deploy MinIO from Helm Chart

To retain Pelorus dashboard data in the long-term, we'll deploy an instance of [minio](https://github.com/helm/charts/tree/master/stable/minio) and create a bucket called `thanos`.

```
helm install --namespace minio --set "buckets[0].name=thanos" \
--set "buckets[0].policy=none" \
--set "buckets[0].purge=false" \
--set "configPathmc=/tmp/minio/mc" \
--set "DeploymentUpdate.type=\"Recreate\"" pelorus-minio stable/minio
```

* Recreate mode is used. RollingDeployments won't allow re-deployment while a pvc is in use
* Configuration and certificate path changed to [work with openshift](https://github.com/minio/mc/issues/2640)

### Secure Minio Object Storage

Secure minio using a [service serving certificate](https://docs.openshift.com/container-platform/4.8/security/certificates/service-serving-certificate.html)

```
helm upgrade --namespace minio --set "certsPath=/tmp/minio/certs" \
--set "tls.enabled=true" \
--set "tls.certSecret=pelorus-minio-tls" \
--set "tls.privateKey=tls.key,tls.publicCrt=tls.crt" \
--set "service.annotations.service\.beta\.openshift\.io/serving-cert-secret-name=pelorus-minio-tls" \
--set "DeploymentUpdate.type=\"Recreate\"" pelorus-minio stable/minio
```

### Update Pelorus Configuration

To update our Pelorus stack, run the following script from within the root repository directory.
```
./runhelm.sh -n pelorus \
-s "bucket_access_point=pelorus-minio.minio.svc:9000" \
-s "bucket_access_key=AKIAIOSFODNN7EXAMPLE" \
-s "bucket_secret_access_key=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
```
