# Testing
The OCP resources should be tested via [conftest](https://github.com/open-policy-agent/conftest).
The tests use [BATS](https://github.com/bats-core/bats-core) as a test framework.

## Executing Locally
```
make conf-tests
```

## Policies which already exist
There are two policies repos which are currently pulled via the CI:
- https://github.com/redhat-cop
- https://github.com/swade1987

Policies can also be local to this repo in the policy dir.

## Including a new Policy
Conftest activates policies via the `--namespace` flag.

By default, we use a regex selector. In the example below, we only activate all the `deprecated` policies:
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

As the selector is regex, we can use groups. In the example below, we only activate `deprecated` policies for `4.1` and `4.3`:
```bash
@test "charts/deploy" {
  tmp=$(helm_template "charts/deploy")

  namespaces=$(get_rego_namespaces "(ocp\.deprecated\.ocp4_1.*|ocp\.deprecated\.ocp4_3.*)")
  cmd="conftest test ${tmp} --output tap ${namespaces}"
  run ${cmd}

  print_info "${status}" "${output}" "${cmd}" "${tmp}"
  [ "$status" -eq 0 ]
}
```

It is also possible to active all namespaces via:
```bash
@test "charts/deploy" {
  tmp=$(helm_template "charts/deploy")

  cmd="conftest test ${tmp} --output tap --all-namespaces"
  run ${cmd}

  print_info "${status}" "${output}" "${cmd}" "${tmp}"
  [ "$status" -eq 0 ]
}
```
