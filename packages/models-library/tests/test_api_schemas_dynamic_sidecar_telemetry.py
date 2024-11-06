import psutil
import pytest
from models_library.api_schemas_dynamic_sidecar.telemetry import DiskUsage
from psutil._common import sdiskusage
from pydantic import ByteSize, ValidationError


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


def test_from_efs_guardian_constructor():
    result = DiskUsage.from_efs_guardian(10, 100)
    assert result.used == ByteSize(10)
    assert result.free == ByteSize(90)
    assert result.total == ByteSize(100)
    assert result.used_percent == 10


def test_failing_validation():
    with pytest.raises(ValidationError) as exc:
        assert DiskUsage.from_efs_guardian(100, 10)

    assert "free" in f"{exc.value}"
    assert "input_value=-90" in f"{exc.value}"

    with pytest.raises(ValidationError) as exc:
        assert DiskUsage(
            used=-10,  # type: ignore
            free=ByteSize(10),
            total=ByteSize(0),
            used_percent=-10,
        )
    assert "used" in f"{exc.value}"
    assert "input_value=-10" in f"{exc.value}"

    with pytest.raises(ValidationError) as exc:
        DiskUsage(
            used=ByteSize(10), free=ByteSize(10), total=ByteSize(21), used_percent=0
        )
    assert "is different than the sum of" in f"{exc.value}"
