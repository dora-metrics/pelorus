#!/usr/bin/env bats

load bats-support-clone.sh
load test_helper/bats-support/load
load test_helper/redhatcop-bats-library/load

setup_file() {
  rm -rf /tmp/rhcop
  conftest_pull
}

@test "charts/pelorus" {
  tmp=$(helm_template "pelorus-operator/helm-charts/pelorus")

  namespaces=$(get_rego_namespaces "ocp\.deprecated\.*")
  cmd="conftest test ${tmp} --output tap ${namespaces}"
  run ${cmd}

  print_info "${status}" "${output}" "${cmd}" "${tmp}"
  [ "$status" -eq 0 ]
}
