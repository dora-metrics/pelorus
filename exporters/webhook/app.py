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

import http
import importlib
import logging
import time as _time
from collections import OrderedDict
from pathlib import Path
from typing import Iterable, Optional

from attrs import field, frozen
from fastapi import FastAPI, Header, HTTPException, Request
from prometheus_client import Counter, Histogram, CONTENT_TYPE_LATEST, generate_latest
from prometheus_client.core import REGISTRY
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse as StarletteJSONResponse, Response

import pelorus
from pelorus.config import env_vars, load_and_log
from pelorus.config.log import REDACT, log
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
    _MAX_METRICS,
    PelorusGaugeMetricFamily,
    in_memory_commit_metrics,
    in_memory_deploy_timestamp_metric,
    in_memory_failure_creation_metric,
    in_memory_failure_resolution_metric,
    pelorus_metric_to_prometheus,
)

WEBHOOK_DIR = Path(__file__).resolve().parent

plugins: dict[str, type[PelorusWebhookPlugin]] = {}


def register_plugin(webhook_plugin: type[PelorusWebhookPlugin]):
    try:
        is_pelorus_plugin = getattr(webhook_plugin, "is_pelorus_webhook_handler", None)
        has_register = getattr(webhook_plugin, "register", None)
        if callable(is_pelorus_plugin) and callable(has_register):
            plugin_user_agent = webhook_plugin.register()
            plugins[plugin_user_agent] = webhook_plugin
            logging.info(
                "Registered webhook plugin for user-agent: '%s'", plugin_user_agent
            )
    except NotImplementedError:
        logging.warning("Could not register plugin: %s", webhook_plugin, exc_info=True)


def load_plugins(plugins_dir_name: Optional[str] = "plugins"):
    plugin_dir_path = WEBHOOK_DIR / plugins_dir_name
    package_path = f"webhook.{plugins_dir_name}"
    logging.info("Loading plugins from directory %s", plugin_dir_path)
    if plugin_dir_path.is_dir():
        for filename in plugin_dir_path.iterdir():
            if filename.is_file() and filename.name.endswith("_handler.py"):
                module = importlib.import_module(
                    f".{filename.stem}", package=package_path
                )
                for name in dir(module):
                    obj = getattr(module, name)
                    if isinstance(obj, type) and issubclass(obj, PelorusWebhookPlugin) and obj is not PelorusWebhookPlugin:
                        register_plugin(obj)
    else:
        logging.warning("Wrong plugin directory %s", plugin_dir_path)


webhook_received = Counter("webhook_received_total", "Number of received webhooks")
webhook_processed = Counter("webhook_processed_total", "Number of processed webhooks")
webhook_errors = Counter("webhook_errors_total", "Number of webhook processing errors")
webhook_request_duration = Histogram(
    "webhook_request_duration_seconds",
    "Latency of webhook request processing",
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)


@frozen
class WebhookCollector(pelorus.AbstractPelorusExporter):
    """
    Collector for webhook-based Prometheus metrics.
    """

    secret_token: Optional[str] = field(
        default=None, metadata=env_vars("SECRET_TOKEN") | log(REDACT), repr=False
    )

    def describe(self) -> list[PelorusGaugeMetricFamily]:
        return [
            in_memory_commit_metrics,
            in_memory_deploy_timestamp_metric,
            in_memory_failure_creation_metric,
            in_memory_failure_resolution_metric,
        ]

    def collect(self) -> Iterable[PelorusGaugeMetricFamily]:
        yield in_memory_commit_metrics
        yield in_memory_deploy_timestamp_metric
        yield in_memory_failure_creation_metric
        yield in_memory_failure_resolution_metric


async def prometheus_metric(received_metric: PelorusMetric):
    try:
        received_metric_type = received_metric.metric_spec
        metric = received_metric.metric_data
        prom_labels = pelorus_metric_to_prometheus(metric)

        if received_metric_type == PelorusMetricSpec.COMMIT_TIME:
            commit_metric_id = f"{metric.namespace}:{metric.app}:{metric.image_sha}:{metric.commit_hash}"
            in_memory_commit_metrics.add_metric(
                commit_metric_id, prom_labels, metric.timestamp
            )
        elif received_metric_type == PelorusMetricSpec.DEPLOY_TIME:
            metric_id = f"{metric.namespace}:{metric.app}:{metric.image_sha}:{metric.timestamp}"
            in_memory_deploy_timestamp_metric.add_metric(
                metric_id, prom_labels, metric.timestamp
            )
        elif received_metric_type == PelorusMetricSpec.FAILURE:
            failure_type = metric.failure_event
            metric_id = f"{metric.failure_id}:{metric.timestamp}"

            if failure_type == FailurePelorusPayload.FailureEvent.CREATED:
                in_memory_failure_creation_metric.add_metric(
                    metric_id,
                    prom_labels,
                    metric.timestamp,
                )
            elif failure_type == FailurePelorusPayload.FailureEvent.RESOLVED:
                in_memory_failure_resolution_metric.add_metric(
                    metric_id,
                    prom_labels,
                    metric.timestamp,
                )
            else:
                logging.error(
                    "Failure Metric of type %s can not be stored: app=%s, failure_id=%s",
                    type(metric).__name__,
                    getattr(metric, 'app', 'unknown'),
                    getattr(metric, 'failure_id', 'unknown'),
                )
                webhook_errors.inc()
                return
        else:
            logging.error(
                "Metric of type %s can not be stored: app=%s, spec=%s",
                type(metric).__name__,
                getattr(metric, 'app', 'unknown'),
                received_metric_type,
            )
            webhook_errors.inc()
            return
        webhook_processed.inc()
        logging.info(
            "Webhook processed: type=%s, app=%s",
            received_metric_type.value if hasattr(received_metric_type, 'value') else received_metric_type,
            getattr(metric, 'app', 'unknown'),
        )
    except Exception:
        logging.error("Failed to process webhook metric", exc_info=True)
        webhook_errors.inc()
        raise


_handler_cache: OrderedDict[str, Optional[type[PelorusWebhookPlugin]]] = OrderedDict()
_HANDLER_CACHE_MAX = 1_000


async def get_handler(user_agent: str) -> Optional[type[PelorusWebhookPlugin]]:
    if user_agent in _handler_cache:
        _handler_cache.move_to_end(user_agent)
        return _handler_cache[user_agent]
    result: Optional[type[PelorusWebhookPlugin]] = None
    for handler in plugins.values():
        if handler.can_handle(user_agent):
            result = handler
            break
    if len(_handler_cache) >= _HANDLER_CACHE_MAX:
        _handler_cache.popitem(last=False)
    _handler_cache[user_agent] = result
    return result


MAX_BODY_SIZE = 100_000  # 100KB


class LimitRequestBodyMiddleware(BaseHTTPMiddleware):
    """Reject requests whose actual body exceeds MAX_BODY_SIZE."""

    async def dispatch(self, request: Request, call_next):
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return await call_next(request)
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > MAX_BODY_SIZE:
                    logging.warning(
                        "Rejected request: Content-Length %s exceeds limit %d",
                        content_length, MAX_BODY_SIZE,
                    )
                    return StarletteJSONResponse(
                        {"detail": "Content too large."},
                        status_code=http.HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                    )
            except ValueError:
                return StarletteJSONResponse(
                    {"detail": "Invalid Content-Length header."},
                    status_code=http.HTTPStatus.BAD_REQUEST,
                )
        body = await request.body()
        if len(body) > MAX_BODY_SIZE:
            logging.warning(
                "Rejected request: body size %d exceeds limit %d",
                len(body), MAX_BODY_SIZE,
            )
            return StarletteJSONResponse(
                {"detail": "Content too large."},
                status_code=http.HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            )
        return await call_next(request)


class SecurityHeadersMiddleware:
    """Add standard security headers to all responses (pure ASGI, no body buffering)."""

    _HEADERS = [
        (b"x-content-type-options", b"nosniff"),
        (b"x-frame-options", b"DENY"),
        (b"cache-control", b"no-store"),
    ]

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def inject_headers(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.extend(SecurityHeadersMiddleware._HEADERS)
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, inject_headers)


app = FastAPI(
    title="Pelorus Webhook receiver",
    openapi_url=None,
    docs_url=None,
    redoc_url=None,
)
app.add_middleware(LimitRequestBodyMiddleware)
app.add_middleware(SecurityHeadersMiddleware)


def _get_hash_token() -> Optional[str]:
    return collector.secret_token


@app.post(
    "/pelorus/webhook",
    status_code=http.HTTPStatus.ACCEPTED,
)
async def pelorus_webhook(
    request: Request,
    user_agent: Optional[str] = Header(None),
) -> PelorusWebhookResponse:
    webhook_received.inc()
    start_time = _time.monotonic()

    if not user_agent:
        raise HTTPException(
            status_code=http.HTTPStatus.BAD_REQUEST,
            detail="Missing User-Agent header.",
        )

    sanitized_ua = user_agent.replace("\n", " ").replace("\r", " ")
    logging.debug("User-agent: %s", sanitized_ua)
    webhook_handler = await get_handler(user_agent)
    if not webhook_handler:
        logging.warning(
            "Could not find webhook handler for the user agent: %s", sanitized_ua
        )
        raise HTTPException(
            status_code=http.HTTPStatus.BAD_REQUEST,
            detail="Unsupported User-Agent.",
        )

    handler = webhook_handler(request.headers, request, secret=_get_hash_token())
    handshake = await handler.handshake()
    if not handshake:
        raise HTTPException(
            status_code=http.HTTPStatus.BAD_REQUEST,
            detail="Handshake failed. Check required headers.",
        )

    try:
        received_pelorus_metric = await handler.receive()
    except HTTPException:
        raise
    except Exception as e:
        webhook_errors.inc()
        logging.error("Webhook payload processing error: %s", e, exc_info=True)
        raise HTTPException(
            status_code=http.HTTPStatus.UNPROCESSABLE_ENTITY,
            detail="Invalid webhook payload.",
        )

    try:
        await prometheus_metric(received_pelorus_metric)
    except Exception:
        raise HTTPException(
            status_code=http.HTTPStatus.INTERNAL_SERVER_ERROR,
            detail="Failed to store metric.",
        )
    finally:
        webhook_request_duration.observe(_time.monotonic() - start_time)

    return PelorusWebhookResponse(
        http_response="Webhook Received", http_response_code=http.HTTPStatus.ACCEPTED
    )


@app.get("/health")
async def health():
    status = "ok"
    details = {}

    if not plugins:
        status = "degraded"
        details["plugins"] = "no webhook plugins registered"

    store_counts = {
        "commit_metrics": in_memory_commit_metrics.metric_count,
        "deploy_metrics": in_memory_deploy_timestamp_metric.metric_count,
        "failure_creation_metrics": in_memory_failure_creation_metric.metric_count,
        "failure_resolution_metrics": in_memory_failure_resolution_metric.metric_count,
    }
    total_metrics = sum(store_counts.values())
    utilization_pct = round(total_metrics / _MAX_METRICS * 100, 1) if _MAX_METRICS else 0

    if utilization_pct > 80:
        status = "degraded"
        details["store_warning"] = f"store utilization at {utilization_pct}%"

    details["store"] = store_counts
    details["store_capacity"] = _MAX_METRICS
    details["store_utilization_pct"] = utilization_pct

    body = {"status": status, **details}
    status_code = 503 if status == "degraded" else 200
    return StarletteJSONResponse(content=body, status_code=status_code)


@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


if __name__ == "__main__":
    import uvicorn

    pelorus.setup_logging()

    load_plugins()

    collector = load_and_log(WebhookCollector)

    if not collector.secret_token:
        logging.warning(
            "No SECRET_TOKEN configured. Webhook endpoint accepts "
            "unauthenticated requests. Set SECRET_TOKEN to enable HMAC verification."
        )

    logging.info("PELORUS_WEBHOOK_MAX_METRICS=%d", _MAX_METRICS)

    REGISTRY.register(collector)

    uvicorn.run(app, host="0.0.0.0", port=pelorus.EXPORTER_PORT)
