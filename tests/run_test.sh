#!/bin/bash
oc delete cm pelorus-test-runner || true
oc create cm pelorus-test-runner $(find *.py | sed 's/^\(.*\)$/--from-file=\1/' | sed -e :a -e '$!N; s/\n/ /; ta')
oc apply -f pelorus-test-job.yml
while [ $(oc get pods | grep pelorus-test | grep -c Completed) -ne 1 ]; do
    echo "Waiting for test job to complete"
    sleep 5

    if [ $(oc get pods | grep pelorus-test | grep -c Error) -gt 0 ]; then
        echo "Error detected!"
        JOB_POD=$(oc get pods | grep pelorus-test | grep Error | head -n 1 | awk '{print $1}')
        oc logs $JOB_POD | tee status.txt
        oc delete job pelorus-test
        STATUS=$(tac status.txt | head -n 1)
        #rm -f status.txt
        exit 1
    fi
done
JOB_POD=$(oc get pods | grep pelorus-test | head -n 1 | awk '{print $1}')
oc logs $JOB_POD | tee status.txt
oc delete job pelorus-test
STATUS=$(tac status.txt | head -n 1)
#rm -f status.txt
if [ "$STATUS" != "OK" ]; then
    exit 1
fi
