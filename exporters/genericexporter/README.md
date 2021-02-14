# Generic Exporter (Builds)

The Generic exporter is responsible for collecting the following metric from an associated webhook/mongodb instance:

```
commit_timestamp{app, commit_hash, image_sha} timestamp
```

Deploy an instance of a webhook/mongodb and post build information to the webhook as part of your build. From there, the generic exporter will retrieve the build information from the db and query the respective git provider to get the commit time associated with the build.

Expected data model of build info sent to webhook/mongodb:
```
{"app": "APP NAME", 
"commit":"COMMIT HASH", 
"image_sha":"IMAGE HASH", 
"git_provider": "PROVIDER", (i.e. github, gitlab, bitbucket)
"repo":"REPO URL", 
"branch":"REPO BRANCH"}
```