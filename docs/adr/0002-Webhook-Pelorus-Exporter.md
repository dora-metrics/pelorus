# 2. Webhook pelorus exporter

Date: 2023-03-09

## Status

Accepted

## Context

Currently all Pelorus exporters like failure, committime and deploytime are designed and implemented to use `pull` model to gather the data from external sources such as GitHub, GitLab, Jira, ServiceNow, etc...

The proposal is to allow Pelorus to receive data from the external data sources using, which will use `push` method to send data to the Pelorus.

The benefits of the `push` method:

 - The architecture to integrate 3rd party CI/CD systems is going to be simplified
 - Standardized communication API between 3rd party systems and Pelorus
 - Pelorus gaining the option to receive additional data such as SLA or SLO
 - Possible reduction of the exporter instances, due to generic nature of the webhook exporter in which one instance may serve multiple purposes
 - Less network traffic. Only when an event interesting from the Pelorus perspective happens the information will be sent
 - Reduced number of the OCP priviledges required by the `push` method exporter. The `push` method does not require access to the various OCP resources for querying them

## Decision

We will use an HTTP webhook to implement Pelorus `push` medthod for receiving information.

### Design Overview

The webhook is an additional exporter, that exposes two services, one for receiving data from various external systems such as Jira, GitHub, GitLab, Bitbucket, and others. It then via the second service exposes this data to Prometheus, which will scrape and store the data for Pelorus purposes.

To ensure seamless integration with 3rd party external systems and enforce data validation for the Project, the webhook exporter will include plugins that are specifically designed to communicate with external systems. These plugins will be tailored to the unique requirements of the Pelorus, allowing for efficient and accurate data transmission between the external systems and the Pelorus's Prometheus instance.

### How it works

1. Webhook or if needed multiple webhooks are deployed as additional exporter on it's own or side to other Pelorus exporters
2. One Webhook instance is capable of receiving different metric types such as deploytime, committime, failure
3. The Webhook exporter is capable of receiving data from any external systems that are sending data to the webhook via it's endpoint.
4. The webhook receives the data and transforms it into a Pelorus compatible format
5. The webhook exposes the transformed data to Prometheus by exposing a Prometheus endpoint
6. Prometheus scrapes the webhook's Prometheus endpoint and stores the received data in its time-series database

```
    +-----------------------+      +-----------------------+    +--------------------------+
    |  External System (1)  |      |  External System (2)  |    |  External System (3..N)  |
    +-----------+-----------+      +-----------+-----------+    +-----------+--------------+
                | (send)                       | (send)                     | (send)
            +---+------------------------------+                            |
            |                                                               |
+-----------v-----------+                                       +-----------v-----------+
|       Webhook 1       |                                       |       Webhook 2       |
+-----------^-----------+                                       +-----------^-----------+
            | (scrape)                                                      |
      +-----+------+                                                        | (scrape)
      |            |                                                        |
      | Prometheus +--------------------------------------------------------+
      |            |
      +------------+
```

### Implementation

The webhook is developed in Python programming language. Among the various frameworks considered for the initial implementation, [FastAPI](https://github.com/tiangolo/fastapi) was chosen for the following reasons:

  - FastAPI is capable of handling multiple requests simultaneously and improving performance, thanks to its support for asynchronous code. We translate those requests in an async manner to the Prometheus exporters, which is non-blocking on both sides of the webhook service.
  - It has built-in support for Pydantic to enforce type safety. In Pelorus we already use typing to validate data that is collected and exposed to the Prometheus. This still may be the case, however to validate data coming in from the external systems we will use Pydantic.
  - It has been adopted by several well-known organizations such as Netflix, Microsoft, Uber, Turing.com or FleetOps for their projects.

### Alternatives Considered

[Flask](https://palletsprojects.com/p/flask/) and [Django](https://www.djangoproject.com/) were considered as an implementation framework alternatives.

## Consequences

Good:

  - The webhook exporter enables Pelorus to integrate with external 3rd party systems, enabling it to monitor deployments or components thereof that occur outside the OpenShift pipelines.
  - The webhook exporter provides a simple way to create and validate additional metrics models.
  - Push model of the webhook does not need to access OpenShift internal objects, reducing need for the RBAC access if used.


Bad

  - The responsibility of ensuring the integrity of data transmitted via webhook between different events in the application lifecycle is delegated to the service sending the data, which may result in inaccurate data. For instance, the timestamp of image creation may be more recent than the deployment timestamp, or the deployment image SHA may not be provided by the commit time event.
  - There is potential risk of exposing service via route to the external world.
  - Even if the webhook does not require other exporters RBAC access, the pelorus-operator still needs to specify the entire set of RBAC privileges, to satisfy scenarios for other exporters.

