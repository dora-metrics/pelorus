#!/bin/bash
RULES_FILE="pelorus-operator/helm-charts/pelorus/templates/prometheus-rules.yaml"
TESTS_DIR="_test/prometheus"

# Capture prometheus rules file out to a new temporary file
# since its embedded in a CR.
sed -n '/groups:/,$p' ${RULES_FILE} > ${TESTS_DIR}/rules.yaml

# Must have promtool installed
# https://github.com/prometheus/prometheus/releases
promtool test rules ${TESTS_DIR}/test.yaml
