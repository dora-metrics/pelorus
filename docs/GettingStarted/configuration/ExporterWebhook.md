# Webhook Exporter

The Webhook exporter is capable of receiving data from any service that sends an appropriate HTTP POST request.

The HTTP POST request consists of two parts, [Header and the Payload](#webhook-headers-and-payloads). The Header data specifies which webhook plugin should be used to validate and transform the payload into a Pelorus metric, that is consumed by Prometheus.

The payload data received by the webhook exporter may be any type of data that other exporters has to pull from other providers or OpenShift objects, such as [Failure](./ExporterFailure.md), [Commit Time](./ExporterCommittime.md), [Deploy Time](./ExporterDeploytime.md).

While the webhook exporter can be used on its own, it can also be used in conjunction with other exporters to gather complementary data.

It's important to note that the webhook exporter performs validation of the payload data to check if it complies with the proper format. However, it does not check for data integrity, which is the responsibility of the service sending the HTTP POST request. This means that values like image digests, deployment namespaces, application names, or commit hashes can be anything, and if improper values are sent, they will still be collected and may cause dashboard inconsistencies.

## Example

The webhook exporter configuration option must be placed under `spec.exporters.instances` in the Pelorus configuration object YAML file as in the example, with a non-default [LOG_LEVEL](#log_level) option:

```yaml
apiVersion: charts.pelorus.konveyor.io/v1alpha1
kind: Pelorus
metadata:
  name: example-configuration
spec:
  exporters:
    instances:
      - app_name: webhook-exporter
        exporter_type: webhook
        extraEnv:
          - name: LOG_LEVEL
            value: debug
```

## Webhook endpoint URI

When you deploy the webhook exporter, an OpenShift route with the HTTP endpoint is created. This endpoint allows services to send HTTP POST requests. To access the webhook endpoint, simply add the `/webhook/pelorus` suffix to the HTTP endpoint created during deployment.

To find the URI of this route after deploying the webhook exporter, use the following `oc` command:

```shell
$ oc get routes -n pelorus webhook-exporter
NAME               HOST/PORT             PATH   SERVICES           PORT   TERMINATION   WILDCARD
webhook-exporter   webhook.endpoint.uri         webhook-exporter   http                 None
```

The POST webhook endpoint for the above example: `webhook.endpoint.uri/webhook/pelorus`

## Configuration options

This is the list of options that can be applied to `env_from_secrets`, `env_from_configmaps` and `extraEnv` section of a webhook exporter.

| Variable | Required | Default Value |
|----------|----------|---------------|
| [LOG_LEVEL](#log_level) | no | `INFO` |

###### LOG_LEVEL

- **Required:** no
    - **Default Value:** INFO
- **Type:** string

: Set the log level. One of `DEBUG`, `INFO`, `WARNING`, `ERROR`.

## Webhook headers and payloads

When sending an HTTP POST request to the webhook's configured URL endpoint, the payload must conform to the webhook payload specification and include several special headers. It's important to note that the header specifications may vary depending on the Pelorus plugin determined by the `User-Agent` Header value and are described per plugin, alongside the payload specification.

### `Pelorus-Webhook/`
#### Headers specification

| Header | Description |
|--------|---------------|
| `User-Agent` | Prefix must begin with `Pelorus-Webhook/` in order to use this plugin. |
| `X-Pelorus-Event` | One of [`deploytime`](#deploytime), [`committime`](#committime), [`failure`](#failure). Must match the Payload format, otherwise will fail to be validated and processed. |
| `Content-Type` | Indicates the format of the payload. Currently, only `application/json` is supported. |

#### Payload specification

##### deploytime
For the Header X-Pelorus-Event: `deploytime`

| Key         | Type     | Description |
|-------------|----------|---------------|
| `app`       | `string` | Monitored application name |
| `image_sha` | `string` | Image SHA used for deployment. Must be prefixed with the `sha256:` followed by 64 characters of small letters and numbers |
| `namespace` | `string` | OpenShift namespace to which application was deployed |
| `timestamp` | `int`    | EPOCH timestamp representing event occurrence. Allowed format: `10 digit int`|

##### committime
For the Header X-Pelorus-Event: `committime`

| Key           | Type     | Description |
| ------------- |----------|-------------|
| `app`         | `string` | Monitored application name |
| `commit_hash` | `string` | Source code GIT SHA-1 used to build the image represented by the `image_sha`. Must be either 7 or 40 characters long |
| `image_sha`   | `string` | Image SHA used for deployment. Must be prefixed with the `sha256:` followed by 64 characters of small letters and numbers |
| `namespace`   | `string` | OpenShift namespace to which application was deployed |
| `timestamp`   | `int`    | EPOCH timestamp representing event occurrence. Allowed format: `10 digit int`|

##### failure
For the Header X-Pelorus-Event: `failure`

| Key             | Type     | Description |
|-----------------|----------|-------------|
| `app`           | `string` | Monitored application name |
| `failure_id`    | `string` | Unique string representation of an failure  |
| `failure_event` | `string` | Information about failure event. Allowed string values: `created` or `resolved` |
| `timestamp`     | `int`    | EPOCH timestamp representing event occurrence. Allowed format: `10 digit int`|


## Example usage

You can easily send a POST request using [Curl](https://curl.se) directly from the shell. You can store the payload data in a file or pass it as an argument to [Curl](https://curl.se). Below is an example of sending several requests to cover the lifecycle of an application:

* Our application:
    * is named **`mongo-todolist`** in OpenShift.
    * is deployed to the **`mongo-persistent`** namespace.
    * deployment happened at (EPOCH): **`1678106205`**

    * the container image used for the deployment has SHA **`af4092ccbfa99a3ec1ea93058fe39b8ddfd8db1c7a18081db397c50a0b8ec77d`**

    * commit used to create the above image has GIT commit hash: **`5379bad65a3f83853a75aabec9e0e43c75fd18fc`**
    * commit used to create the above image happened (EPOCH): **`1678105701`**
      ```shell
      $ git show -s --format=%ct 5379bad65a3f83853a75aabec9e0e43c75fd18fc
      1678105701
      ```

    * got a production failure at (EPOCH): **`1678181704`**
    * the production failure was resolved at (EPOCH): **`1678206464`**


The `JSON` files that are consistent with the above scenario and will be used by the curl CLI:

* mongo_committime.json
```json
{
  "app": "mongo-todolist",
  "commit_hash": "5379bad65a3f83853a75aabec9e0e43c75fd18fc",
  "image_sha": "sha256:af4092ccbfa99a3ec1ea93058fe39b8ddfd8db1c7a18081db397c50a0b8ec77d",
  "namespace": "mongo-persistent",
  "timestamp": 1678105701
}
```
* mongo_deploytime.json
```json
{
  "app": "mongo-todolist",
  "image_sha": "sha256:af4092ccbfa99a3ec1ea93058fe39b8ddfd8db1c7a18081db397c50a0b8ec77d",
  "namespace": "mongo-persistent",
  "timestamp": 1678106205
}
```
* mongo_production_failure.json
```json
{
  "app": "mongo-todolist",
  "failure_id": "MONGO-1",
  "failure_event": "created",
  "timestamp": 1678181704
}
```
* mongo_production_failure_resolved.json
```json
{
  "app": "mongo-todolist",
  "failure_id": "MONGO-1",
  "failure_event": "resolved",
  "timestamp": 1678206464
}
```

Sending the payload from the directory where `*.json` files are:

```shell
$ curl -X POST <Webhook route URI>/pelorus/webhook \
       -H "User-Agent: Pelorus-Webhook/test" \
       -H "X-Pelorus-Event: committime" \
       -H "Content-Type: application/json" \
       -d ./mongo_committime.json
```

```shell
$ curl -X POST <Webhook route URI>/pelorus/webhook \
       -H "User-Agent: Pelorus-Webhook/test" \
       -H "X-Pelorus-Event: deploytime" \
       -H "Content-Type: application/json" \
       -d ./mongo_deploytime.json
```

```shell
$ curl -X POST <Webhook route URI>/pelorus/webhook \
       -H "User-Agent: Pelorus-Webhook/test" \
       -H "X-Pelorus-Event: failure" \
       -H "Content-Type: application/json" \
       -d ./mongo_production_failure.json
```

```shell
$ curl -X POST <Webhook route URI>/pelorus/webhook \
       -H "User-Agent: Pelorus-Webhook/test" \
       -H "X-Pelorus-Event: failure" \
       -H "Content-Type: application/json" \
       -d ./mongo_production_failure_resolved.json
```