#!/usr/bin/env bash

# Runs chart-testing (ct CLI) with remote flag to avoid git errors

GIT_REPO=dora-metrics/pelorus.git
REMOTE=origin
ORIGIN=$(git remote show origin)

if [ $? = 0 ]; then
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

ct lint --remote "$REMOTE" --config ct.yaml
