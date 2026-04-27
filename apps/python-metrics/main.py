"""
Sample worker: OTLP metrics to the collector + Prometheus /metrics for scraping.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

from opentelemetry import metrics
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


def _setup_metrics() -> None:
    resource = Resource.create()

    prometheus_reader = PrometheusMetricReader()
    otlp_exporter = OTLPMetricExporter()
    otlp_reader = PeriodicExportingMetricReader(otlp_exporter)

    provider = MeterProvider(
        resource=resource,
        metric_readers=[prometheus_reader, otlp_reader],
    )
    metrics.set_meter_provider(provider)

    meter = metrics.get_meter(__name__)
    messages_counter = meter.create_counter(
        "app_messages_total",
        unit="1",
        description="Total messages processed (OTLP + Prometheus export)",
    )

    def tick() -> None:
        while True:
            messages_counter.add(1, {"result": "ok"})
            time.sleep(5)

    threading.Thread(target=tick, daemon=True).start()


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path in ("/healthz", "/"):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        log.debug("%s - %s", self.address_string(), format % args)


def main() -> None:
    from prometheus_client import start_http_server

    http_port = int(os.environ.get("HTTP_PORT", "8080"))
    metrics_port = int(os.environ.get("METRICS_PORT", "9464"))

    _setup_metrics()
    start_http_server(metrics_port, addr="0.0.0.0")
    log.info("Prometheus metrics on 0.0.0.0:%s/metrics", metrics_port)

    server = HTTPServer(("0.0.0.0", http_port), _HealthHandler)
    log.info("Health on 0.0.0.0:%s/healthz", http_port)
    server.serve_forever()


if __name__ == "__main__":
    main()
