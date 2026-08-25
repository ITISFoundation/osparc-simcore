from prometheus_client import CollectorRegistry
from prometheus_client.metrics import Gauge
from simcore_service_director_v2.modules.instrumentation._models import (
    DynamiSidecarMetrics,
)


def _samples(gauge: Gauge) -> dict[tuple[tuple[str, str], ...], float]:
    return {
        tuple(sorted(sample.labels.items())): sample.value for family in gauge.collect() for sample in family.samples
    }


def test_update_running_services_count_sets_and_removes_stale_labels() -> None:
    metrics = DynamiSidecarMetrics(  # pylint: disable=unexpected-keyword-arg
        subsystem="dynamic_services", registry=CollectorRegistry()
    )

    labels_1 = {
        "user_id": "1",
        "wallet_id": "None",
        "service_key": "simcore/services/dynamic/foo",
        "service_version": "1.0.0",
    }
    labels_2 = {
        "user_id": "2",
        "wallet_id": "5",
        "service_key": "simcore/services/dynamic/bar",
        "service_version": "2.0.0",
    }

    metrics.update_running_services_count([labels_1, labels_1, labels_2])
    samples = _samples(metrics.running_services_count)
    assert samples[tuple(sorted(labels_1.items()))] == 2
    assert samples[tuple(sorted(labels_2.items()))] == 1

    # labels_2 no longer present -> removed entirely, not just zeroed
    metrics.update_running_services_count([labels_1])
    samples = _samples(metrics.running_services_count)
    assert samples[tuple(sorted(labels_1.items()))] == 1
    assert tuple(sorted(labels_2.items())) not in samples

    # nothing running anymore -> no samples left at all
    metrics.update_running_services_count([])
    assert _samples(metrics.running_services_count) == {}
