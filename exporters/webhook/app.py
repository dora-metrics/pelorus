#!/usr/bin/env python3
#
# Copyright Red Hat
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
#

import asyncio
import http
import importlib
import logging
import sys
from pathlib import Path
from typing import Dict, Optional, Type

from attr import field, frozen
from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import PlainTextResponse
from prometheus_client import Counter, generate_latest
from prometheus_client.core import REGISTRY

import pelorus
from pelorus.config import load_and_log
from webhook.models.pelorus_webhook import (
    FailurePelorusPayload,
    PelorusMetric,
    PelorusMetricSpec,
)
from webhook.plugins.pelorus_handler_base import (
    PelorusWebhookPlugin,
    PelorusWebhookResponse,
)
from webhook.store.in_memory_metric import (
    PelorusGaugeMetricFamily,
    in_memory_commit_metrics,
    in_memory_deploy_timestamp_metric,
    in_memory_failure_creation_metric,
    in_memory_failure_resolution_metric,
    pelorus_metric_to_prometheus,
)

# TODO Plugins Module
WEBHOOK_DIR = Path(__file__).resolve().parent

plugins: Dict[str, PelorusWebhookPlugin] = {}


def register_plugin(webhook_plugin: PelorusWebhookPlugin):
    try:
        is_pelorus_plugin = getattr(webhook_plugin, "is_pelorus_webhook_handler", None)
        has_register = getattr(webhook_plugin, "register", None)
        if callable(is_pelorus_plugin) and callable(has_register):
            plugin_user_agent = webhook_plugin.register()
            plugins[plugin_user_agent] = webhook_plugin
            logging.info(
                "Registered webhook plugin for user-agent: '%s'" % plugin_user_agent
            )
    except NotImplementedError:
        logging.warning("Could not register plugin: %s" % str(webhook_plugin))


def load_plugins(plugins_dir_name: Optional[str] = "plugins"):
    plugin_dir_path = WEBHOOK_DIR / plugins_dir_name
    sys.path.append(WEBHOOK_DIR.as_posix())
    logging.info(f"Loading plugins from directory {plugin_dir_path}")
    if plugin_dir_path.is_dir():
        for filename in plugin_dir_path.iterdir():
            if filename.is_file() and filename.name.endswith("_handler.py"):
                module = importlib.import_module(
                    f".{filename.stem}", package=f"{plugins_dir_name}"
                )
                for name in dir(module):
                    obj = getattr(module, name)
                    if isinstance(obj, type):
                        # Do not register base class
                        if str(obj.__name__) == "PelorusWebhookPlugin":
                            continue
                        register_plugin(obj)
    else:
        logging.warning(f"Wrong plugin directory {plugin_dir_path}")


# TODO Metrics Module
webhook_received = Counter("webhook_received_total", "Number of received webhooks")
webhook_processed = Counter("webhook_processed_total", "Number of processed webhooks")


@frozen
class WebhookCollector(pelorus.AbstractPelorusExporter):
    """
    Base class for a WebHook collector.
    """

    secret_token: str = field(default=None)

    def collect(self) -> PelorusGaugeMetricFamily:
        yield in_memory_commit_metrics
        yield in_memory_deploy_timestamp_metric
        yield in_memory_failure_creation_metric
        yield in_memory_failure_resolution_metric


async def prometheus_metric(received_metric: PelorusMetric):
    received_metric_type = received_metric.metric_spec
    metric = received_metric.metric_data
    prometheus_metric = pelorus_metric_to_prometheus(metric)

    if received_metric_type == PelorusMetricSpec.COMMIT_TIME:
        in_memory_commit_metrics.add_metric(
            metric.commit_hash, prometheus_metric, metric.timestamp
        )
    elif received_metric_type == PelorusMetricSpec.DEPLOY_TIME:
        metric_id = f"{metric.app}{metric.timestamp}"
        in_memory_deploy_timestamp_metric.add_metric(
            metric_id, prometheus_metric, metric.timestamp, timestamp=metric.timestamp
        )
    elif received_metric_type == PelorusMetricSpec.FAILURE:
        failure_type = metric.failure_event
        metric_id = f"{metric.failure_id}{metric.timestamp}"

        if failure_type == FailurePelorusPayload.FailureEvent.CREATED:
            in_memory_failure_creation_metric.add_metric(
                metric_id, prometheus_metric, metric.timestamp
            )
        elif failure_type == FailurePelorusPayload.FailureEvent.RESOLVED:
            in_memory_failure_resolution_metric.add_metric(
                metric_id, prometheus_metric, metric.timestamp
            )
        else:
            logging.error(f"Failure Metric {metric} can not be stored")
    else:
        logging.error(f"Metric {metric} can not be stored")
        return
    # Increase the number of webhooks processed
    webhook_processed.inc()
    logging.debug("Webhook processed")


# TODO Config Module
def allowed_hosts(request: Request) -> bool:
    # Raise exception if the request is not from allowed hosts
    return True


async def get_handler(user_agent: str) -> Optional[Type[PelorusWebhookPlugin]]:
    for handler in plugins.values():
        if handler.can_handle(user_agent):
            return handler
    return None


# TODO App Module
app = FastAPI(
    title="Pelorus Webhook receiver",
    openapi_url=None,
    docs_url=None,
    redoc_url=None,
)


def _get_hash_token() -> str:
    return collector.secret_token


@app.post(
    "/pelorus/webhook",
    status_code=http.HTTPStatus.ACCEPTED,
    dependencies=[Depends(allowed_hosts)],
)
async def pelorus_webhook(
    request: Request,
    response: Response,
    payload: dict,
    user_agent: str = Header(None),
    content_length: int = Header(...),
) -> PelorusWebhookResponse:
    webhook_received.inc()

    if content_length > 100000:
        raise HTTPException(
            status_code=http.HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            detail="Content length too big.",
        )

    logging.debug("User-agent: %s" % user_agent)
    webhook_handler = await get_handler(user_agent)
    if not webhook_handler:
        logging.warning(
            "Could not find webhook handler for the user agent: %s" % user_agent
        )
        raise HTTPException(
            status_code=http.HTTPStatus.PRECONDITION_FAILED,
            detail="Unsupported request.",
        )

    handler = webhook_handler(request.headers, request, secret=_get_hash_token())
    handshake = await handler.handshake()
    if not handshake:
        raise HTTPException(
            status_code=http.HTTPStatus.BAD_REQUEST,
            detail="We don't talk the same language.",
        )

    received_pelorus_metric = await handler.receive()

    asyncio.create_task(prometheus_metric(received_pelorus_metric))

    return PelorusWebhookResponse(
        http_response="Webhook Received", http_response_code=http.HTTPStatus.OK
    )


@app.get("/{path:path}", response_class=PlainTextResponse)
async def metrics():
    return generate_latest()


if __name__ == "__main__":
    import uvicorn

    pelorus.setup_logging()

    load_plugins()

    collector = load_and_log(WebhookCollector)

    REGISTRY.register(collector)

    uvicorn.run(app, host="0.0.0.0", port=8080)
