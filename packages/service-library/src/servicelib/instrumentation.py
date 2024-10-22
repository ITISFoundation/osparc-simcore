from dataclasses import dataclass

from prometheus_client import CollectorRegistry


@dataclass(slots=True, kw_only=True)
class MetricsBase:
    subsystem: str
    registry: CollectorRegistry


def get_metrics_namespace(application_name: str) -> str:
    return application_name.replace("-", "_")
