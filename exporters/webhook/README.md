# Webhook Exporter

A simple Webhook exporter written using FastAPI and pydantic that exposes metrics to the prometheus endpoint.

Currently only some of the commit time data is received, no SSL/salt to secure the data. It's PoC.

## Testing

```shell
$ make dev-env
$ source .venv/bin/activate
$ export LOG_LEVEL=debug
$ python exporters/webhook/app.py
```

To send some data you can use simple curl:
```shell
$ cd exporters/tests/data

# Set times when the events actually happens

# Commit happened 1 day ago:
$ COMMIT_EVENT_TIMESTAMP=$(date -d '1 day ago' +%s)

# Deploy event must have happened maximum 30min ago:
$ DEPLOY_EVENT_TIMESTAMP=$(date -d '20 min ago' +%s)

# Failure happened just after deployment, let's say 19min ago
$ FAILURE_CREATE_TIMESTAMP=$(date -d '19 min ago' +%s)

# Failure was resolved now
$ FAILURE_RESOLVED_TIMESTAMP=$(date +%s)

# Copy test files to the temp directory, so we don't modify the ones from the git repository
$ TMP_DIR=$(mkfile -d)
$ cp webhook_pelorus_*.json "$TMP_DIR"
$ pushd "$TMP_DIR"

# Modify the temporary files with the proper timestamps
$ sed -i "s/\"timestamp\":.*/\"timestamp\": $COMMIT_EVENT_TIMESTAMP/" ./webhook_pelorus_committime.json
$ sed -i "s/\"timestamp\":.*/\"timestamp\": $DEPLOY_EVENT_TIMESTAMP/" ./webhook_pelorus_deploytime.json
$ sed -i "s/\"timestamp\":.*/\"timestamp\": $FAILURE_CREATE_TIMESTAMP/" ./webhook_pelorus_failure_created.json
$ sed -i "s/\"timestamp\":.*/\"timestamp\": $FAILURE_RESOLVED_TIMESTAMP/" ./webhook_pelorus_failure_resolved.json


# Send the events to the webhook endpoint

$ curl -X POST http://localhost:8080/pelorus/webhook -d @./webhook_pelorus_committime.json -H "Content-Type: application/json" -H "User-Agent: Pelorus-Webhook/test" -H "X-Pelorus-Event: committime"
$ curl -X POST http://localhost:8080/pelorus/webhook -d @./webhook_pelorus_deploytime.json -H "Content-Type: application/json" -H "User-Agent: Pelorus-Webhook/test" -H "X-Pelorus-Event: deploytime"
$ curl -X POST http://localhost:8080/pelorus/webhook -d @./webhook_pelorus_failure_created.json -H "Content-Type: application/json" -H "User-Agent: Pelorus-Webhook/test" -H "X-Pelorus-Event: failure"
$ curl -X POST http://localhost:8080/pelorus/webhook -d @./webhook_pelorus_failure_resolved.json -H "Content-Type: application/json" -H "User-Agent: Pelorus-Webhook/test" -H "X-Pelorus-Event: failure"
```

Navigate to the endpoint [http://localhost:8080/metrics](http://localhost:8080/metrics), you should see all the metrics, similar to:
```
# HELP commit_timestamp Commit timestamp
# TYPE commit_timestamp gauge
commit_timestamp{app="mongo-todolist",commit_hash="5379bad65a3f83853a75aabec9e0e43c75fd18fc",image_sha="sha256:af4092ccbfa99a3ec1ea93058fe39b8ddfd8db1c7a18081db397c50a0b8ec77d",namespace="mongo-persistent"} 1.682936938e+09
# HELP deploy_timestamp Deployment timestamp
# TYPE deploy_timestamp gauge
deploy_timestamp{app="mongo-todolist",image_sha="sha256:af4092ccbfa99a3ec1ea93058fe39b8ddfd8db1c7a18081db397c50a0b8ec77d",namespace="mongo-persistent"} 1.683022138e+09 1683022138000
# HELP failure_creation_timestamp Failure Creation Timestamp
# TYPE failure_creation_timestamp gauge
failure_creation_timestamp{app="mongo-todolist",failure_id="MONGO-1"} 1.683022198e+09
# HELP failure_resolution_timestamp Failure Resolution Timestamp
# TYPE failure_resolution_timestamp gauge
failure_resolution_timestamp{app="mongo-todolist",failure_id="MONGO-1"} 1.683023338e+09
```
