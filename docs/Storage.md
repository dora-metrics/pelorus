# Long Term Storage

The following will walk through the deployment of long term storage for pelours.

### Prerequisites

Before deploying the tooling, you must have the following prepared

* An OpenShift 3.11 or higher Environment
* A machine from which to run the install (usually your laptop)
  * The OpenShift Command Line Tool (oc)
  * [Helm3](https://github.com/helm/helm/releases)
  * An updated helm chart repo (LINK)

### Deployment Instructions
To deploy Pelorus with long term storage, run the following script from within the root repository directory


#### 1. Add a security context to OpenShift

[INSERT STEP FOR THIS]

#### 2. Install Minio Helm Chart 

(https://github.com/helm/charts/tree/master/stable/minio)

```
helm install --set "buckets[0].name=thanos,buckets[0].policy=none,buckets[0].purge=false,configPathmc=/tmp/minio/mc" tolarewa-minio stable/minio
```

* Explain why we need to change config path

#### 3. Secure Minio Using Openshift Service Signed Cert

```
helm upgrade --set "certsPath=/tmp/minio/certs,tls.enabled=true,tls.certSecret=tolarewa-minio-ssl,tls.privateKey=tls.key,tls.publicCrt=tls.crt,service.annotations.service\.beta\.openshift\.io/serving-cert-secret-name=tolarewa-minio-ssl" tolarewa-minio stable/minio
```

 * Explain why we need to change certs path to tmp folder

#### 4. Install Pelorus w/ Long Term Storage

```
 ./runhelm.sh -n pelorus-tolarewa -s "bucket_access_point=tolarewa-minio.pelorus-tolarewa.svc:9000,bucket_access_key=AKIAIOSFODNN7EXAMPLE,bucket_secret_access_key=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
 ```

#### 5. 

