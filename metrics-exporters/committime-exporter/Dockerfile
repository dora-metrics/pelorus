FROM python:3.8-slim
#FROM registry.redhat.io/ubi8/python-36

MAINTAINER Aly Ibrahim<aly@redhat.com>

RUN mkdir -p exporter

COPY requirements.txt exporter/

RUN pip install --no-cache-dir -r exporter/requirements.txt

COPY app.py exporter/app.py

EXPOSE 8080

ENTRYPOINT ["python", "exporter/app.py" ]


