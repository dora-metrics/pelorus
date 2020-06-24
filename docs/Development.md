# Pelorus Development Guide

We appreciate your interest in contributing to Pelorus! Use this guide to help you get up and running.

There are three main tracks of Pelorus development to consider.

1. [Deployment Automation](#contributing-to-deployment-development)
    
    This track mostly involves testing, fixing, and updating our Helm chart(s) to streamline the installation and configuration experience. Knowledge of Helm, OpenShift, Operators and Prometheus configuration is assumed for this work.
1. [Dashboard Development](#dashboard-development)

    This is where we take the raw data we've collected and turn it into actionable visual representations that will help IT organizations make important decisions. Knowledge of Grafana and PromQL is required for contribution here.
1. [Exporter Development](#exporter-development)

    This track is focused around the development of custom [Prometheus exporters](https://prometheus.io/docs/instrumenting/writing_exporters/) to gather the information we need in order to calculate our core metrics. Python development experience is assumed.

## Contributing to Deployment Automation

We use [Helm](https://helm.sh) to provide an automated deployment and configuration experience for Pelorus. We are always doing work to cover more and more complex use cases with our helm charts. In order to be able to effectively contribute to these charts, you'll need a cluster that satisfies all of the installation prerequisites for Pelorus.

See the [Install guide](/docs/Install.md) for more details on that.

Currently we have two charts:

1. The [deploy](/charts/deploy/) chart managed the core stack, which includes:
    * Prometheus Operator
    * Prometheus
    * Thanos
    * Grafana Operator
    * Grafana
2. The [exporter](/charts/exporter) chart handles all exporter deployments. Which exporter gets deployed is determined by the `values.yaml` file passed in.

## Dashboard Development

TODO

## Exporter Development

A Pelorus exporter is simply a [Prometheus exporter](https://prometheus.io/docs/instrumenting/writing_exporters/). While they can technically be written in many languages, we've written ours in Python using the [Prometheus python client](https://github.com/prometheus/client_python) library. We chose Python because it seems to be the most popular programming language for operations teams.

### Exporter directory layout

The following is a minimal directory structure for a Pelorus exporter.

```
exporters/exporter/
├── app.py
├── __init__.py
├── lib_pelorus -> ../lib_pelorus
├── README.md
└── values.yaml
```

### Running locally

Running an exporter on your local machine should follow this process:

1. Install dependencies

        pip install -r exporters/requirements.txt

1. Set any environment variables required (or desired) for the given exporter (see [Configuring Exporters](docs/Configuration.md#configuring-exporters) to see supported variables).

1. Start the exporter
        
        python exporters/committime/app.py

At this point, your exporter should be available at http://localhost:8080

    curl http://localhost:8080

### IDE Setup (VSCode)

Most of us use Visual Studio Code to do our python development. The following extensions for VSCode are useful. Each can be installed by hitting `Ctrl+P` and pasting the commands below.

* [Markdown Preview Github Styling](https://marketplace.visualstudio.com/items?itemName=bierner.markdown-preview-github-styles)

        ext install bierner.markdown-preview-github-styles
* [Python](https://marketplace.visualstudio.com/items?itemName=ms-python.python)

        ext install ms-python.python
   

Code also comes with a nice debugger feature. Here is a starter configuration to use with our exporters. Just create a file called `.vscode/launch.json` in your `pelorus/` project directory with the following content.

```
{
    // Use IntelliSense to learn about possible attributes.
    // Hover to view descriptions of existing attributes.
    // For more information, visit: https://go.microsoft.com/fwlink/?linkid=830387
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Commit Time Exporter",
            "type": "python",
            "request": "launch",
            "program": "${workspaceFolder}/exporters/committime/app.py",
            "console": "integratedTerminal",
            "env": {
                "GITHUB_USER": "<github username here>", 
                "GITHUB_TOKEN": "<personal access token here>",
                "LOG_LEVEL": "INFO",
                "APP_LABEL": "app.kubernetes.io/name"
            }
        },
        {
            "name": "Deploy Time Exporter",
            "type": "python",
            "request": "launch",
            "program": "${workspaceFolder}/exporters/deploytime/app.py",
            "console": "integratedTerminal",
            "env": {
                "LOG_LEVEL": "INFO",
                "APP_LABEL": "app.kubernetes.io/name"
            }        },
        {
            "name": "Deploy Time Exporter",
            "type": "python",
            "request": "launch",
            "program": "${workspaceFolder}/exporters/failure/app.py",
            "console": "integratedTerminal",
            "env": {
                "SERVER": "<Jira server url>",
                "PROJECT": "<Jira project ID>",
                "USER": "<Jira username>",
                "TOKEN": "<Jira personal access token>",
                "LOG_LEVEL": "INFO",
                "APP_LABEL": "app.kubernetes.io/name"
            }
        }
    ]
}
```

For more information, see the [Debugging](https://code.visualstudio.com/docs/editor/debugging) doc in VS Code.
