#!/usr/bin/env bats

load bats-support-clone
load test_helper/bats-support/load
load test_helper/redhatcop-bats-library/load

setup_file() {
  rm -rf /tmp/rhcop
  conftest_pull
}

@test "charts/deploy" {
  tmp=$(helm_template "charts/deploy")

  namespaces=$(get_rego_namespaces "ocp\.deprecated\.*")
  cmd="conftest test ${tmp} --output tap ${namespaces}"
  run ${cmd}

  print_info "${status}" "${output}" "${cmd}" "${tmp}"
  [ "$status" -eq 0 ]
}

@test "charts/exporter" {
  tmp=$(helm_template "charts/exporter")

  namespaces=$(get_rego_namespaces "ocp\.deprecated\.*")
  cmd="conftest test ${tmp} --output tap ${namespaces}"
  run ${cmd}

  print_info "${status}" "${output}" "${cmd}" "${tmp}"
  [ "$status" -eq 0 ]
}

@test "storage/minio-scc.yaml" {
  tmp=$(split_files "storage/minio-scc.yaml")

  namespaces=$(get_rego_namespaces "ocp\.deprecated\.*")
  cmd="conftest test ${tmp} --output tap ${namespaces}"
  run ${cmd}

  print_info "${status}" "${output}" "${cmd}" "${tmp}"
  [ "$status" -eq 0 ]
}