import psutil
import pytest
from models_library.api_schemas_dynamic_sidecar.telemetry import DiskUsage
from psutil._common import sdiskusage


def _assert_same_value(ps_util_disk_usage: sdiskusage) -> None:
    disk_usage = DiskUsage.from_ps_util_disk_usage(ps_util_disk_usage)
    assert disk_usage.used == ps_util_disk_usage.used
    assert disk_usage.free == ps_util_disk_usage.free
    assert disk_usage.used_percent == pytest.approx(ps_util_disk_usage.percent, abs=1e3)


@pytest.mark.parametrize(
    "ps_util_disk_usage",
    [
        sdiskusage(total=77851254784, used=58336940032, free=19497537536, percent=74.9),
        sdiskusage(total=77851254784, used=58573619200, free=19260858368, percent=75.3),
        sdiskusage(total=77851254784, used=58573529088, free=19260948480, percent=75.3),
        sdiskusage(total=77851254784, used=58573664256, free=19260813312, percent=75.3),
    ],
)
def test_disk_usage_regression_cases(ps_util_disk_usage: sdiskusage):
    _assert_same_value(ps_util_disk_usage)


def test_disk_usage():
    ps_util_disk_usage = psutil.disk_usage("/")
    _assert_same_value(ps_util_disk_usage)
