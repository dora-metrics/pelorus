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
$ curl -X POST http://localhost:8000/pelorus/webhook -d @./webhook_pelorus_committime.json -H "Content-Type: application/json" -H "User-Agent: Pelorus-Webhook/test" -H "X-Pelorus-Event: committime"
$ curl -X POST http://localhost:8000/pelorus/webhook -d @./webhook_pelorus_deploytime.json -H "Content-Type: application/json" -H "User-Agent: Pelorus-Webhook/test" -H "X-Pelorus-Event: deploytime"
$ curl -X POST http://localhost:8000/pelorus/webhook -d @./webhook_pelorus_failure_created.json -H "Content-Type: application/json" -H "User-Agent: Pelorus-Webhook/test" -H "X-Pelorus-Event: failure"
$ curl -X POST http://localhost:8000/pelorus/webhook -d @./webhook_pelorus_failure_resolved.json -H "Content-Type: application/json" -H "User-Agent: Pelorus-Webhook/test" -H "X-Pelorus-Event: failure"
```

Navigate to the endpoint [http://localhost:8000/metrics](http://localhost:8000/metrics), you should see all the metrics collected:
```
# HELP commit_timestamp Commit timestamp
# TYPE commit_timestamp gauge
commit_timestamp{app="mongo-todolist",commit_hash="5379bad65a3f83853a75aabec9e0e43c75fd18fc",image_sha="sha256:af4092ccbfa99a3ec1ea93058fe39b8ddfd8db1c7a18081db397c50a0b8ec77d",namespace="mongo-persistent"} 1.557933657e+09
# HELP deploy_timestamp Deployment timestamp
# TYPE deploy_timestamp gauge
deploy_timestamp{app="mongo-todolist",image_sha="sha256:af4092ccbfa99a3ec1ea93058fe39b8ddfd8db1c7a18081db397c50a0b8ec77d",namespace="mongo-persistent"} 1.557933657e+09
# HELP failure_creation_timestamp Failure Creation Timestamp
# TYPE failure_creation_timestamp gauge
failure_creation_timestamp{app="mongo-todolist",failure_id="MONGO-1"} 1.557933657e+09
# HELP failure_resolution_timestamp Failure Resolution Timestamp
# TYPE failure_resolution_timestamp gauge
failure_resolution_timestamp{app="mongo-todolist",failure_id="MONGO-1"} 1.557933657e+09
```
