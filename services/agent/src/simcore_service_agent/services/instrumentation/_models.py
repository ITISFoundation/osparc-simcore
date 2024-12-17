from dataclasses import dataclass, field
from typing import Final

from models_library.docker import DockerNodeID
from prometheus_client import CollectorRegistry, Counter
from servicelib.instrumentation import MetricsBase, get_metrics_namespace

from ..._meta import APP_NAME

_METRICS_NAMESPACE: Final[str] = get_metrics_namespace(APP_NAME)
_LABELS_COUNTERS: Final[tuple[str, ...]] = ("docker_node_id",)


@dataclass(slots=True, kw_only=True)
class AgentMetrics(MetricsBase):
    volumes_removed: Counter = field(init=False)
    volumes_backedup: Counter = field(init=False)

    def __post_init__(self) -> None:
        self.volumes_removed = Counter(
            "volumes_removed_total",
            "Number of removed volumes by the agent",
            labelnames=_LABELS_COUNTERS,
            namespace=_METRICS_NAMESPACE,
            subsystem=self.subsystem,
            registry=self.registry,
        )

        self.volumes_backedup = Counter(
            "volumes_backedup_total",
            "Number of removed volumes who's content was uplaoded by the agent",
            labelnames=_LABELS_COUNTERS,
            namespace=_METRICS_NAMESPACE,
            subsystem=self.subsystem,
            registry=self.registry,
        )

    def remove_volumes(self, docker_node_id: DockerNodeID) -> None:
        self.volumes_removed.labels(docker_node_id=docker_node_id).inc()

    def backedup_volumes(self, docker_node_id: DockerNodeID) -> None:
        self.volumes_backedup.labels(docker_node_id=docker_node_id).inc()


@dataclass(slots=True, kw_only=True)
class AgentInstrumentation:
    registry: CollectorRegistry
    agent_metrics: AgentMetrics = field(init=False)

    def __post_init__(self) -> None:
        self.agent_metrics = AgentMetrics(  # pylint: disable=unexpected-keyword-arg
            subsystem="agent", registry=self.registry
        )
