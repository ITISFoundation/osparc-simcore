from typing import Final

from servicelib.instrumentation import get_metrics_namespace

from ..._meta import APP_NAME

METRICS_NAMESPACE: Final[str] = get_metrics_namespace(APP_NAME)
PRIMARY_INSTANCE_LABELS: Final[tuple[str, ...]] = ("instance_type", "user_id", "wallet_id")

PRIMARY_INSTANCES_METRICS_DEFINITIONS: Final[dict[str, tuple[str, tuple[str, ...]]]] = {
    "starting_instances": (
        "Number of primary EC2 instances that were launched and are awaiting deployment/connection",
        PRIMARY_INSTANCE_LABELS,
    ),
    "connected_instances": (
        "Number of primary EC2 instances whose dask-scheduler is reachable",
        PRIMARY_INSTANCE_LABELS,
    ),
    "busy_instances": (
        "Number of primary EC2 instances whose dask-scheduler is currently running tasks",
        PRIMARY_INSTANCE_LABELS,
    ),
    "broken_instances": (
        "Number of primary EC2 instances that were connected but are now unresponsive and pending termination",
        PRIMARY_INSTANCE_LABELS,
    ),
}
