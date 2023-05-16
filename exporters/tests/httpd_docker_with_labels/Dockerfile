FROM quay.io/centos7/httpd-24-centos7

ARG LAST_COMMIT_DATE_TIME
ARG LAST_COMMIT_SHA

LABEL io.openshift.build.commit.date=${LAST_COMMIT_DATE_TIME}
LABEL io.openshift.build.commit.id=${LAST_COMMIT_SHA}
LABEL io.openshift.build.source-location="https://github.com/dora-metrics/pelorus"
