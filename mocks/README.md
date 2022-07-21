# Mockserver

The mock server allows you to test any of the exporters against mockup endpoints of different sources (github, gitlab, jira, etc)

## Start up the mock server

The mock server can be started using the [Mockoon GUI](https://mockoon.com/docs/latest/gui-cheat-sheet/) or the [Mockoon CLI](https://github.com/mockoon/cli#installation) or using a container with the [Mockoon CLI](https://hub.docker.com/r/mockoon/cli).

Let's start the mock server using the container approach.

First, you will need to install a container engine like [Podman](https://podman.io/)

Then clone this repository and execute the following command to startup the mock server.

```sh
$ git clone https://github.com/konveyor/pelorus.git
```

```sh
$ podman run --name mockoon --rm -v <path-to-repo>/pelorus/mocks/commitexporter_github.json:/data:z -p 3000:3000 mockoon/cli:latest -d data -i 0

Mock started at https://localhost:3000 (pid: 0, name: mockoon-openshift)
```

### Test against the mock server

Set up your envs in order to use the mock server.

```sh
export API_USER=gituser
export TOKEN=gittoken
export GIT_API=localhost:3000
export LOG_LEVEL=DEBUG
export NAMESPACES=basic-nginx-build,basic-nginx-dev,basic-nginx-stage,basic-nginx-prod
export TLS_VERIFY=False
```
---
**NOTE**

The env TLS_VERIFY is needed because the mocks server use a self-signed certificate.

---

Because the commit exporters search on Openshift the information from the build, first you need to execute "oc login" against the mock server

```sh
$ oc login --token=sha256~r07jPULrwSJLQGjinp9tSNi4Lq4cqKOSCjl7QeDPxOc --server=https://localhost:3000

Logged into "https://localhost:3000" as "admin" using the token provided.

You have access to 64 projects, the list has been suppressed. You can list all projects with 'oc projects'

Using project "default".
```
Finally, execute the exporter

```sh
$ python exporters/committime/app.py

Initializing Logger wit LogLevel: INFO
...
05-13-2021 11:02:47 INFO     =====Using GitHub Collector=====
05-13-2021 11:02:47 INFO     Using non-default API: localhost:3000
05-13-2021 11:02:47 INFO     Watching namespaces: ['basic-nginx-build', 'basic-nginx-dev', 'basic-nginx-stage', 'basic-nginx-prod']
...
05-13-2021 11:02:48 INFO     Collected commit_timestamp{ namespace=basic-nginx-build, app=basic-nginx, commit=15dedb60b6208aafdfb2328a93543e3d94500978, image_sha=sha256:c1282f65b5c327db4dcc6cdfb27e91338bd625d119d9ae769318f089d82e35e2 } 1619381788.0
05-13-2021 11:02:48 INFO     Collected commit_timestamp{ namespace=basic-nginx-build, app=basic-nginx, commit=15dedb60b6208aafdfb2328a93543e3d94500978, image_sha=sha256:4a20c8cfa48af3a938462e9cd7bfa0b16abfbc6ba16f0999f3931c79b1130e4b } 1619381788.0
05-13-2021 11:02:48 INFO     Collected commit_timestamp{ namespace=basic-nginx-build, app=basic-nginx, commit=620ce8b570c644338ba34224fc09b2d8a30bca02, image_sha=sha256:71309995e6da43b76079a649b00e0aa8378443e72f1fccc76af0d73d67a7f644 } 1620401174.0
```

Verify the result by going into the following URL http://localhost:8080/ 

You should get this result:

```sh
# HELP python_gc_objects_collected_total Objects collected during gc
# TYPE python_gc_objects_collected_total counter
python_gc_objects_collected_total{generation="0"} 1858.0
python_gc_objects_collected_total{generation="1"} 610.0
python_gc_objects_collected_total{generation="2"} 470.0
# HELP python_gc_objects_uncollectable_total Uncollectable object found during GC
# TYPE python_gc_objects_uncollectable_total counter
python_gc_objects_uncollectable_total{generation="0"} 0.0
python_gc_objects_uncollectable_total{generation="1"} 0.0
python_gc_objects_uncollectable_total{generation="2"} 0.0
# HELP python_gc_collections_total Number of times this generation was collected
# TYPE python_gc_collections_total counter
python_gc_collections_total{generation="0"} 243.0
python_gc_collections_total{generation="1"} 22.0
python_gc_collections_total{generation="2"} 2.0
# HELP python_info Python platform information
# TYPE python_info gauge
python_info{implementation="CPython",major="3",minor="9",patchlevel="4",version="3.9.4"} 1.0
# HELP process_virtual_memory_bytes Virtual memory size in bytes.
# TYPE process_virtual_memory_bytes gauge
process_virtual_memory_bytes 1.681764352e+09
# HELP process_resident_memory_bytes Resident memory size in bytes.
# TYPE process_resident_memory_bytes gauge
process_resident_memory_bytes 8.423424e+07
# HELP process_start_time_seconds Start time of the process since unix epoch in seconds.
# TYPE process_start_time_seconds gauge
process_start_time_seconds 1.62091816459e+09
# HELP process_cpu_seconds_total Total user and system CPU time spent in seconds.
# TYPE process_cpu_seconds_total counter
process_cpu_seconds_total 2.23
# HELP process_open_fds Number of open file descriptors.
# TYPE process_open_fds gauge
process_open_fds 28.0
# HELP process_max_fds Maximum number of open file descriptors.
# TYPE process_max_fds gauge
process_max_fds 8192.0
# HELP commit_timestamp Commit timestamp
# TYPE commit_timestamp gauge
commit_timestamp{app="basic-nginx",commit="15dedb60b6208aafdfb2328a93543e3d94500978",image_sha="sha256:c1282f65b5c327db4dcc6cdfb27e91338bd625d119d9ae769318f089d82e35e2",namespace="basic-nginx-build"} 1.619381788e+09
# HELP commit_timestamp Commit timestamp
# TYPE commit_timestamp gauge
commit_timestamp{app="basic-nginx",commit="15dedb60b6208aafdfb2328a93543e3d94500978",image_sha="sha256:c1282f65b5c327db4dcc6cdfb27e91338bd625d119d9ae769318f089d82e35e2",namespace="basic-nginx-build"} 1.619381788e+09
commit_timestamp{app="basic-nginx",commit="15dedb60b6208aafdfb2328a93543e3d94500978",image_sha="sha256:4a20c8cfa48af3a938462e9cd7bfa0b16abfbc6ba16f0999f3931c79b1130e4b",namespace="basic-nginx-build"} 1.619381788e+09
# HELP commit_timestamp Commit timestamp
# TYPE commit_timestamp gauge
commit_timestamp{app="basic-nginx",commit="15dedb60b6208aafdfb2328a93543e3d94500978",image_sha="sha256:c1282f65b5c327db4dcc6cdfb27e91338bd625d119d9ae769318f089d82e35e2",namespace="basic-nginx-build"} 1.619381788e+09
commit_timestamp{app="basic-nginx",commit="15dedb60b6208aafdfb2328a93543e3d94500978",image_sha="sha256:4a20c8cfa48af3a938462e9cd7bfa0b16abfbc6ba16f0999f3931c79b1130e4b",namespace="basic-nginx-build"} 1.619381788e+09
commit_timestamp{app="basic-nginx",commit="620ce8b570c644338ba34224fc09b2d8a30bca02",image_sha="sha256:71309995e6da43b76079a649b00e0aa8378443e72f1fccc76af0d73d67a7f644",namespace="basic-nginx-build"} 1.620401174e+09
```

## Create or edit mock scenarios

In order to create or edit mock scenarios, it's recommended to use the [Mockoon GUI](https://mockoon.com/docs/latest/gui-cheat-sheet/)

### Create new scenarios

To start creating new scenarios you can start by checking the following documentation https://mockoon.com/docs/latest/about/

New scenarios should be added into the [mocks folder](/mocks)

### Import mocks into the UI

To import the samples that are on the [mocks folder](/mocks/) use the following instructions https://mockoon.com/docs/latest/import-export-data/


