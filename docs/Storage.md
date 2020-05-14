# Long Term Storage

The Pelorus chart supports deploying a thanos instance for long term storage.  It can use any S3 bucket provider. The following is an example of configuring a values.yaml file for noobaa with the local s3 service name:

```
bucket_access_point: s3.noobaa.svc
bucket_access_key: <your access key>
bucket_secret_access_key: <your secret access key>
```

The default bucket name is thanos.  It can be overriden by specifying an additional value for the bucket name as in:

```
bucket_access_point: s3.noobaa.svc
bucket_access_key: <your access key>
bucket_secret_access_key: <your secret access key>
thanos_bucket_name: <bucket name here>
```

Then pass this to runhelm.sh like this:

```
./runhelm.sh -v values.yaml
```

The thanos instance can also be configured by setting the same variables as arguments to the installation script:

```
./runhelm.sh -s bucket_access_point=$INTERNAL_S3_ENDPOINT -s bucket_access_key=$AWS_ACCESS_KEY -s bucket_secret_access_key=$AWS_SECRET_ACCESS_KEY -s thanos_bucket_name=somebucket
```


And then:

```
./runhelm.sh -v file_with_bucket_config.yaml
```
