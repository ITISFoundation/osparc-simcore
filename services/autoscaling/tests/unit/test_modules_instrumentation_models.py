from dataclasses import is_dataclass

import pytest
from simcore_service_autoscaling.models import BufferPool, Cluster
from simcore_service_autoscaling.modules.instrumentation._models import (
    BufferPoolsMetrics,
    ClusterMetrics,
)


@pytest.mark.parametrize(
    "class_name, metrics_class_name",
    [(Cluster, ClusterMetrics), (BufferPool, BufferPoolsMetrics)],
)
def test_models_are_in_sync(class_name: type, metrics_class_name: type):
    assert is_dataclass(class_name)
    assert is_dataclass(metrics_class_name)
    for field in class_name.__dataclass_fields__:
        assert hasattr(metrics_class_name, field)
