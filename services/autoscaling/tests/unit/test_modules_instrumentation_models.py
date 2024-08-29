from dataclasses import is_dataclass

import pytest
from simcore_service_autoscaling.models import BufferPool, Cluster
from simcore_service_autoscaling.modules.instrumentation._constants import (
    BUFFER_POOLS_METRICS_DEFINITIONS,
    CLUSTER_METRICS_DEFINITIONS,
)
from simcore_service_autoscaling.modules.instrumentation._models import (
    BufferPoolsMetrics,
    ClusterMetrics,
)


@pytest.mark.parametrize(
    "class_name, metrics_class_name, metrics_definitions",
    [
        (Cluster, ClusterMetrics, CLUSTER_METRICS_DEFINITIONS),
        (BufferPool, BufferPoolsMetrics, BUFFER_POOLS_METRICS_DEFINITIONS),
    ],
)
def test_models_are_in_sync(
    class_name: type,
    metrics_class_name: type,
    metrics_definitions: dict[str, tuple[str, tuple[str, ...]]],
):
    assert is_dataclass(class_name)
    assert is_dataclass(metrics_class_name)
    for field in class_name.__dataclass_fields__:
        assert (
            field in metrics_definitions
        ), f"{metrics_definitions.__qualname__} is missing {field}"
        assert hasattr(
            metrics_class_name, field
        ), f"{metrics_class_name.__qualname__} is missing {field}"
