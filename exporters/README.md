# Metrics Exporters (in development)

Before deploying, you must export your GITHUB_REPOS, GITHUB_USER and GITHUB_TOKEN to your shell. Then run:

    oc process -f templates/github-secret.yaml -p GITHUB_USER=${GITHUB_USER} -p GITHUB_TOKEN=${GITHUB_TOKEN} -p GITHUB_REPOS=${GITHUB_REPOS} | oc apply -f-
    oc process -f templates/exporter.yaml -p APP_NAME=commit-exporter | oc apply -f-

Configuration can be found in the [config guide](https://pelorus.readthedocs.io/en/latest/Configuration/).
