"""OTel 采集 + Prometheus 自定义指标。生产关键一环：可观测性。"""
from __future__ import annotations

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.motor import MotorInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from prometheus_client import Counter, Histogram, Gauge

from .config import get_settings


def setup_otel(app) -> None:
    s = get_settings()
    if not s.OTEL_ENABLED:
        return
    resource = Resource(attributes={SERVICE_NAME: s.OTEL_SERVICE_NAME})
    provider = TracerProvider(resource=resource)
    try:
        exporter = OTLPSpanExporter(endpoint=s.OTEL_EXPORTER_OTLP_ENDPOINT, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(exporter))
    except Exception:  # pragma: no cover - 本地启动 OTel 不在线不阻塞
        pass
    trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(app)
    try:
        MotorInstrumentor().instrument()
        RedisInstrumentor().instrument()
        HTTPXClientInstrumentor().instrument()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Prometheus Metrics（复用 demos/harness 定义 + 生产新增）
# ---------------------------------------------------------------------------

RUNS_TOTAL = Counter('harness_runs_total', 'Total runs triggered',
                     ['scenario_id', 'gate_level', 'status'])
RUN_DURATION = Histogram('harness_run_duration_seconds', 'Run 端到端耗时',
                         ['gate_level'], buckets=[1, 5, 15, 60, 180, 600, 1800])
TOKENS_TOTAL = Counter('harness_tokens_total', 'LLM tokens consumed',
                       ['model', 'scenario_id'])
COST_USD_TOTAL = Counter('harness_cost_usd_total', 'Dollar cost accumulated', ['model'])

GATE_DECISIONS = Counter('harness_gate_decisions_total',
                         'Pass/Fail counts', ['gate_level', 'verdict'])
ANALYZER_FINDINGS = Counter('harness_analyzer_findings_total',
                            'Failure modes detected', ['tag', 'severity'])

SCENARIO_COUNT = Gauge('harness_scenarios_total', 'Active scenarios count', ['status'])
QUEUE_LAG = Gauge('harness_celery_queue_length', 'Celery queue pending messages', ['queue'])

API_LATENCY = Histogram('harness_api_duration_seconds',
                        'API endpoint latency', ['method', 'path', 'status'],
                        buckets=[0.005, 0.02, 0.05, 0.2, 0.5, 1, 5])
API_REQUESTS = Counter('harness_api_requests_total',
                       'API request count', ['method', 'path', 'status'])
