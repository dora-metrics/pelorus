# Build Webhook

This webhook is a flask app and connects to a mongodb instance. For authentication, a `WEBHOOK_SECRET` will be created that will need to be added as a bearer token when posting data to the `/post/build` endpoint.

Update the values.yaml file when deploying Pelorus to deploy an instance of the webhook/mongodb. This is useful in cases where you are performing your builds outside of Openshift and still want to collect commit time metric information. Deploy the Generic Exporter to export data to the Pelorus dashboard alongside this webhook.

Expected data model of build info sent to webhook/mongodb is below. The records are associated with a TTL of 1 Hour (it is expected that Prometheus will scrape the data before the TTL expires, so this db is acting more as a cache and less as a long-term storage solution).

```
{"app": "APP NAME", 
"commit":"COMMIT HASH", 
"image_sha":"IMAGE HASH", 
"git_provider": "PROVIDER", (i.e. github, gitlab, bitbucket)
"repo":"REPO URL", 
"branch":"REPO BRANCH"}
```