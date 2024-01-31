import psutil
from models_library.api_schemas_dynamic_sidecar.telemetry import DiskUsage


def test_disk_usage():
    ps_util_disk_usage = psutil.disk_usage("/")
    disk_usage = DiskUsage.from_ps_util_disk_usage(ps_util_disk_usage)
    assert disk_usage.used == ps_util_disk_usage.used
    assert disk_usage.free == ps_util_disk_usage.free
    assert round(disk_usage.used_percent, 1) == round(ps_util_disk_usage.percent, 1)
