#!/usr/bin/env bash

GIT_REPO=dora-metrics/pelorus.git
REMOTE=origin
ORIGIN=$(git remote show origin)
ORIGIN_RET=$?

if [ $ORIGIN_RET == 0 ]; then
    if ! echo "$ORIGIN" | grep "$GIT_REPO" &> /dev/null; then
        REMOTE=upstream
    fi
fi
git remote add "$REMOTE" "https://github.com/$GIT_REPO" &> /dev/null
if ! git remote show "$REMOTE" | grep "$GIT_REPO" &> /dev/null; then
    echo "git remote repository named $REMOTE already exists and does not point to $GIT_REPO"
    exit 1
fi
git config "remote.$REMOTE.fetch" "+refs/heads/*:refs/remotes/$REMOTE/*"
git fetch "$REMOTE" --unshallow &> /dev/null
git remote update upstream --prune &> /dev/null

# Enforce version bump on exporters

# TODO DEBUG
echo DEBUG DEBUG DEBUG
git rev-parse --abbrev-ref HEAD
git --no-pager diff origin/HEAD --name-status exporters/
echo DEBUG DEBUG DEBUG
# TODO DEBUG

if git status exporters | grep exporters &> /dev/null || git --no-pager diff origin/HEAD --name-status exporters/ | grep exporters &> /dev/null; then
  EXPORT_VERSION_IN_MASTER="$(curl https://raw.githubusercontent.com/dora-metrics/pelorus/master/exporters/setup.py &> /dev/null)"
  CURRENT_EXPORT_VERSION="$(grep '    version="' exporters/setup.py  | cut -c 14- | rev | cut -c 3- | rev)"
  if $EXPORT_VERSION_IN_MASTER | grep "$CURRENT_EXPORT_VERSION" &> /dev/null; then
    # TODO breaks when updating from 2.0.10-rc.1 to 2.0.10, for example
    echo "Exporters version needs a bump!"
    exit 1
  fi

  CURRENT_CHART_VERSION="$(grep '^version: ' charts/pelorus/Chart.yaml  | cut -c 10-)"
  if [[ "$CURRENT_CHART_VERSION" != "$CURRENT_EXPORT_VERSION" ]]; then
    echo "Exporters ($CURRENT_EXPORT_VERSION) and Charts ($CURRENT_CHART_VERSION) versions are not the same!"
    exit 1
  fi
fi

# Runs chart-testing (ct CLI) with remote flag to avoid git errors

ct lint --remote "$REMOTE" --config ct.yaml

# Verify the versions of the charts are the same across main charts and
# the charts from pelorus-operator

# Get the number representing all different versions found in the 'Chart.yaml'
# files within charts/ and pelorus-operator/helm-charts/ directories
FILES_VERSIONS=$(find charts/ pelorus-operator/helm-charts/ -type f -name 'Chart.yaml' -exec grep -H '^version: ' {} \;)
VERSIONS=$(echo "$FILES_VERSIONS" | cut -d ' ' -f 2 | sort | uniq)
NO_VERSIONS=$(echo "$VERSIONS" | wc -l)
if [[ "$NO_VERSIONS" -eq 1 ]]; then
    echo "All chart versions are in-sync. Chart version: $VERSIONS"
else
  echo "ERROR: Found different versions in Chart.yaml files:"
  echo "$FILES_VERSIONS"
  exit 1
fi

# Ensure version of the Grafana and Prometheus operators is in sync
# with pelorus-operator.

GRAFANA_VER_HELM=$(grep grafana_subscription_version charts/operators/values.yaml | cut -d':' -f2 | tr -d ' ')
PROMETHEUS_VER_HELM=$(grep prometheus_subscription_version charts/operators/values.yaml | cut -d':' -f2 | tr -d ' ')

if ! grep \""$GRAFANA_VER_HELM"\" pelorus-operator/bundle/metadata/properties.yaml >/dev/null; then
  echo "ERROR: Grafana version $GRAFANA_VER_HELM not found in the pelorus-operator/bundle/metadata/properties.yaml"
  exit 1
else
  echo "OK: Grafana version $GRAFANA_VER_HELM in sync with the pelorus-operator/bundle/metadata/properties.yaml"
fi

if ! grep \""$PROMETHEUS_VER_HELM"\" pelorus-operator/bundle/metadata/properties.yaml >/dev/null; then
  echo "ERROR: Prometheus version $PROMETHEUS_VER_HELM not found in the pelorus-operator/bundle/metadata/properties.yaml"
  exit 1
else
  echo "OK: Prometheus version $PROMETHEUS_VER_HELM in sync with the pelorus-operator/bundle/metadata/properties.yaml"
fi
