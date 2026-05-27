# Mock Servers

Mock servers allow you to test exporters against mockup endpoints of different providers (GitHub, GitLab, Gitea, Jira, Bitbucket) without needing real credentials or API access.

## Available Mocks

| Mock | Port | Provider | Exporter |
|---|---|---|---|
| `commitexporter_github.json` | 3000 | GitHub | Commit Time |
| `bitbucket_cloud.json` | 3001 | Bitbucket Cloud | Commit Time |
| `commitexporter_gitlab.json` | 3002 | GitLab | Commit Time |
| `commitexporter_gitea.json` | 3003 | Gitea | Commit Time |
| `failure_jira.json` | 3004 | Jira | Failure |
| `failure_github.json` | 3005 | GitHub Issues | Failure |

## Start up the mock server

The mock server can be started using the [Mockoon GUI](https://mockoon.com/docs/latest/gui-cheat-sheet/), the [Mockoon CLI](https://github.com/mockoon/cli#installation), or a container with the [Mockoon CLI](https://hub.docker.com/r/mockoon/cli).

### Using Docker/Podman

```bash
# GitHub commit exporter mock (port 3000)
docker run --rm -d --name mockoon-github \
  -v $(pwd)/mocks/commitexporter_github.json:/data:z \
  -p 3000:3000 mockoon/cli:latest -d data -i 0

# GitLab commit exporter mock (port 3002)
docker run --rm -d --name mockoon-gitlab \
  -v $(pwd)/mocks/commitexporter_gitlab.json:/data:z \
  -p 3002:3002 mockoon/cli:latest -d data -i 0

# Gitea commit exporter mock (port 3003)
docker run --rm -d --name mockoon-gitea \
  -v $(pwd)/mocks/commitexporter_gitea.json:/data:z \
  -p 3003:3003 mockoon/cli:latest -d data -i 0

# Jira failure exporter mock (port 3004)
docker run --rm -d --name mockoon-jira \
  -v $(pwd)/mocks/failure_jira.json:/data:z \
  -p 3004:3004 mockoon/cli:latest -d data -i 0

# GitHub Issues failure exporter mock (port 3005)
docker run --rm -d --name mockoon-gh-issues \
  -v $(pwd)/mocks/failure_github.json:/data:z \
  -p 3005:3005 mockoon/cli:latest -d data -i 0

# Bitbucket Cloud commit exporter mock (port 3001)
docker run --rm -d --name mockoon-bitbucket \
  -v $(pwd)/mocks/bitbucket_cloud.json:/data:z \
  -p 3001:3001 mockoon/cli:latest -d data -i 0
```

### Run all mocks at once

```bash
for mock in mocks/*.json; do
  name=$(basename "$mock" .json)
  port=$(python3 -c "import json; print(json.load(open('$mock'))['port'])")
  docker run --rm -d --name "mockoon-${name}" \
    -v "$(pwd)/${mock}:/data:z" \
    -p "${port}:${port}" mockoon/cli:latest -d data -i 0
  echo "Started ${name} on port ${port}"
done
```

## Testing against mock servers

### GitHub commit exporter

```bash
export API_USER=gituser
export TOKEN=gittoken
export GIT_API=localhost:3000
export GIT_PROVIDER=github
export LOG_LEVEL=DEBUG
export TLS_VERIFY=False
python exporters/committime/app.py
```

### GitLab commit exporter

```bash
export TOKEN=glpat-mock-token
export GIT_API=http://localhost:3002
export GIT_PROVIDER=gitlab
export LOG_LEVEL=DEBUG
export TLS_VERIFY=False
python exporters/committime/app.py
```

### Gitea commit exporter

```bash
export TOKEN=gitea-mock-token
export GIT_API=http://localhost:3003
export GIT_PROVIDER=gitea
export LOG_LEVEL=DEBUG
export TLS_VERIFY=False
python exporters/committime/app.py
```

### Jira failure exporter

```bash
export SERVER=http://localhost:3004
export API_USER=admin
export TOKEN=jira-mock-token
export PROVIDER=jira
export PROJECTS=PROJ
export LOG_LEVEL=DEBUG
python exporters/failure/app.py
```

### GitHub Issues failure exporter

```bash
export TOKEN=ghp-mock-token
export SERVER=http://localhost:3005
export PROVIDER=github
export PROJECTS=pelorus-test/basic-nginx
export LOG_LEVEL=DEBUG
python exporters/failure/app.py
```

## Run automated mock tests

```bash
./scripts/run-mockoon-tests.sh
```

This starts the GitHub mock on port 3000, runs `pytest -m mockoon`, and cleans up.

To run against a specific mock, set `MOCK_JSON`:

```bash
MOCK_JSON=mocks/commitexporter_gitlab.json ./scripts/run-mockoon-tests.sh
```

## Create or edit mock scenarios

Use the [Mockoon GUI](https://mockoon.com/docs/latest/gui-cheat-sheet/) to create or edit scenarios. Import existing mocks via [Import/Export](https://mockoon.com/docs/latest/import-export-data/). New scenarios should be added to the `mocks/` folder.
