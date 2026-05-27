# Testing

## Python Unit Tests

Run the exporter test suite with pytest:

```bash
uv run pytest exporters/tests/ \
  --ignore=exporters/tests/integration \
  --ignore=exporters/tests/certs \
  -p no:pylama -o "addopts="
```

## Prometheus Rules Tests

Prometheus recording rules can be tested with `promtool`:

```bash
# Install promtool from https://github.com/prometheus/prometheus/releases
./_test/test_prometheusrules.sh
```

This extracts the rules from the Helm chart and runs them against the test cases in `_test/prometheus/test.yaml`.

## Conftest (OPA Policy Tests)

OCP resources are tested via [conftest](https://github.com/open-policy-agent/conftest) using [BATS](https://github.com/bats-core/bats-core) as a test framework.

### Executing Locally

```bash
make conf-tests
```

### Policies

Two external policy repos are pulled via CI:
- https://github.com/redhat-cop
- https://github.com/swade1987

Local policies can be added to the `policy/` directory.

### Including a new Policy

Conftest activates policies via the `--namespace` flag with a regex selector:

```bash
@test "charts/deploy" {
  tmp=$(helm_template "charts/deploy")

  namespaces=$(get_rego_namespaces "ocp\.deprecated\.*")
  cmd="conftest test ${tmp} --output tap ${namespaces}"
  run ${cmd}

  print_info "${status}" "${output}" "${cmd}" "${tmp}"
  [ "$status" -eq 0 ]
}
```

## Mock Server Tests

Run integration tests against Mockoon mock servers:

```bash
# GitHub mock (default)
./scripts/run-mockoon-tests.sh

# Other providers
MOCK_JSON=mocks/commitexporter_gitlab.json ./scripts/run-mockoon-tests.sh
```

See `mocks/README.md` for details on available mocks and how to run them.
