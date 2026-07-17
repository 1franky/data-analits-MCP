"""Prometheus metrics for query execution, exposed via GET /metrics."""

from prometheus_client import Counter, Gauge, Histogram

QUERY_REQUESTS_TOTAL = Counter(
    "data_platform_query_requests_total",
    "Total de solicitudes de consulta procesadas.",
    labelnames=("engine", "operation", "status"),
)
QUERY_DURATION_SECONDS = Histogram(
    "data_platform_query_duration_seconds",
    "Duración de ejecución en el adaptador, en segundos.",
    labelnames=("engine", "operation"),
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30),
)
QUERY_QUEUE_WAIT_SECONDS = Histogram(
    "data_platform_query_queue_wait_seconds",
    "Espera para adquirir el semáforo de concurrencia.",
    labelnames=("engine",),
    buckets=(0, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60),
)
QUERY_IN_PROGRESS = Gauge(
    "data_platform_query_in_progress",
    "Consultas en ejecución en este momento.",
    labelnames=("engine",),
)
QUERY_BLOCKED_TOTAL = Counter(
    "data_platform_query_blocked_total",
    "Solicitudes bloqueadas por validación, por motivo.",
    labelnames=("engine", "reason_code"),
)
