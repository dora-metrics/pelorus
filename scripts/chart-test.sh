#!/usr/bin/env bash

GIT_REPO=dora-metrics/pelorus.git
REMOTE=origin
HELP_MESSAGE="INFO: Run scripts/update_projects_version.py to fix it"
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

# Enforce chart version bump when exporters folder is touched

CURRENT_CHART_VERSION="$(grep '^version: ' pelorus-operator/helm-charts/pelorus/Chart.yaml | cut -c 10-)"
if ! git --no-pager diff --quiet $REMOTE/main --name-status exporters/; then
  CHART_FILE_IN_MAIN="$(curl https://raw.githubusercontent.com/dora-metrics/pelorus/main/pelorus-operator/helm-charts/pelorus/Chart.yaml 2> /dev/null)"
  CHART_VERSION_IN_MAIN=$(echo "$CHART_FILE_IN_MAIN" | grep '^version: ' | cut -c 10-)
  if [ "$CHART_VERSION_IN_MAIN" == "$CURRENT_CHART_VERSION" ]; then
    echo "ERROR: Exporters were modified, Charts need version bumping!"
    echo "$HELP_MESSAGE"
    exit 1
  fi
fi

# Runs chart-testing (ct CLI) with remote flag to avoid git errors

ct lint --remote "$REMOTE" --config ct.yaml || exit 1
rm -f pelorus-operator/helm-charts/pelorus/charts/*.tgz

if ! grep "default \"v$CURRENT_CHART_VERSION\"" pelorus-operator/helm-charts/pelorus/charts/exporters/templates/_deployment.yaml &> /dev/null; then
  echo "ERROR: Version in pelorus-operator/helm-charts/pelorus/charts/exporters/templates/_deployment.yaml differs!"
  echo "$HELP_MESSAGE"
  exit 1
fi

if ! grep "default \"v$CURRENT_CHART_VERSION\"" pelorus-operator/helm-charts/pelorus/charts/exporters/templates/_imagestream_from_image.yaml &> /dev/null; then
  echo "ERROR: Version in pelorus-operator/helm-charts/pelorus/charts/exporters/templates/_imagestream_from_image.yaml differs!"
  echo "$HELP_MESSAGE"
  exit 1
fi

# Enforce operator version bump when charts folder is touched

CURRENT_OPERATOR_VERSION="$(grep "^VERSION ?= " pelorus-operator/Makefile  | cut -c 12-)"
if ! git --no-pager diff --quiet $REMOTE/main --name-status pelorus-operator/helm-charts/; then
  OPERATOR_MAKEFILE_IN_MAIN="$(curl https://raw.githubusercontent.com/dora-metrics/pelorus/main/pelorus-operator/Makefile 2> /dev/null)"
  OPERATOR_VERSION_IN_MAIN=$(echo "$OPERATOR_MAKEFILE_IN_MAIN" | grep "^VERSION ?= " | cut -c 12-)
  if [ "$OPERATOR_VERSION_IN_MAIN" == "$CURRENT_OPERATOR_VERSION" ]; then
    echo "ERROR: Charts were modified, Operator needs version bumping!"
    echo "$HELP_MESSAGE"
    exit 1
  fi
fi

# Check if both release candidate versions are the same
# This also enforces that versions are both rc or both release
# shellcheck disable=SC2207
CURRENT_CHART_VERSION_ARRAY=( $(echo "$CURRENT_CHART_VERSION" | tr ' \-rc '  '  ') )
CURRENT_CHART_VERSION_RC_VER=${CURRENT_CHART_VERSION_ARRAY[1]}
# shellcheck disable=SC2207
CURRENT_OPERATOR_VERSION_ARRAY=( $(echo "$CURRENT_OPERATOR_VERSION" | tr ' \-rc '  '  ') )
CURRENT_OPERATOR_VERSION_RC_VER=${CURRENT_OPERATOR_VERSION_ARRAY[1]}
if [ "$CURRENT_CHART_VERSION_RC_VER" != "$CURRENT_OPERATOR_VERSION_RC_VER" ]; then
  echo "ERROR: Release candidate versions differs between charts (rc$CURRENT_CHART_VERSION_RC_VER) and operator (rc$CURRENT_OPERATOR_VERSION_RC_VER)!"
  echo "$HELP_MESSAGE"
  exit 1
fi
