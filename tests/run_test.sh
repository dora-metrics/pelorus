#!/bin/bash
oc delete cm pelorus-test-runner || true
oc create cm pelorus-test-runner --from-file=pelorus_test_runner.py
oc apply -f pelorus-test-job.yml
while [ $(oc get pods | grep pelorus-test | grep -c Completed) -ne 1 ]; do
    echo "Waiting for test job to complete"
    sleep 5
done
JOB_POD=$(oc get pods | grep pelorus-test | awk '{print $1}')
oc logs $JOB_POD | tee status.txt
oc delete job pelorus-test
STATUS=$(tac status.txt | head -n 1)
rm -f status.txt
if [ "$STATUS" != "OK" ]; then
    exit 1
fi
