from typing import Final

from servicelib.instrumentation import get_metrics_namespace

from ..._meta import APP_NAME

METRICS_NAMESPACE: Final[str] = get_metrics_namespace(APP_NAME)
EC2_INSTANCE_LABELS: Final[tuple[str, ...]] = ("instance_type",)

CLUSTER_METRICS_DEFINITIONS: Final[dict[str, tuple[str, tuple[str, ...]]]] = {
    "active_nodes": (
        "Number of EC2-backed docker nodes which are active and ready to run tasks",
        EC2_INSTANCE_LABELS,
    ),
    "pending_nodes": (
        "Number of EC2-backed docker nodes which are active and NOT ready to run tasks",
        EC2_INSTANCE_LABELS,
    ),
    "drained_nodes": (
        "Number of EC2-backed docker nodes which are drained",
        EC2_INSTANCE_LABELS,
    ),
    "hot_buffer_drained_nodes": (
        "Number of EC2-backed docker nodes which are drained and in buffer/reserve",
        EC2_INSTANCE_LABELS,
    ),
    "pending_ec2s": (
        "Number of EC2 instances not yet part of the cluster",
        EC2_INSTANCE_LABELS,
    ),
    "broken_ec2s": (
        "Number of EC2 instances that failed joining the cluster",
        EC2_INSTANCE_LABELS,
    ),
    "warm_buffer_ec2s": (
        "Number of buffer EC2 instances prepared, stopped, and ready to be activated",
        EC2_INSTANCE_LABELS,
    ),
    "disconnected_nodes": (
        "Number of docker nodes not backed by a running EC2 instance",
        (),
    ),
    "terminating_nodes": (
        "Number of EC2-backed docker nodes that started the termination process",
        EC2_INSTANCE_LABELS,
    ),
    "retired_nodes": (
        "Number of EC2-backed docker nodes that were actively retired and waiting for draining and termination or re-use",
        EC2_INSTANCE_LABELS,
    ),
    "terminated_instances": (
        "Number of EC2 instances that were terminated (they are typically visible 1 hour)",
        EC2_INSTANCE_LABELS,
    ),
}

WARM_BUFFER_POOLS_METRICS_DEFINITIONS: Final[dict[str, tuple[str, tuple[str, ...]]]] = {
    "ready_instances": (
        "Number of EC2 buffer instances that are ready for use",
        EC2_INSTANCE_LABELS,
    ),
    "pending_instances": (
        "Number of EC2 buffer instances that are pending/starting",
        EC2_INSTANCE_LABELS,
    ),
    "waiting_to_pull_instances": (
        "Number of EC2 buffer instances that are waiting to pull docker images",
        EC2_INSTANCE_LABELS,
    ),
    "waiting_to_stop_instances": (
        "Number of EC2 buffer instances that are waiting to be stopped",
        EC2_INSTANCE_LABELS,
    ),
    "pulling_instances": (
        "Number of EC2 buffer instances that are actively pulling docker images",
        EC2_INSTANCE_LABELS,
    ),
    "stopping_instances": (
        "Number of EC2 buffer instances that are stopping",
        EC2_INSTANCE_LABELS,
    ),
    "broken_instances": (
        "Number of EC2 buffer instances that are deemed as broken",
        EC2_INSTANCE_LABELS,
    ),
}
