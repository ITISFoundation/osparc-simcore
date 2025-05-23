import logging

from fastapi import FastAPI
from models_library.api_schemas_dynamic_sidecar.telemetry import DiskUsage
from pydantic import validate_call
from servicelib.rabbitmq import RPCRouter

from ...modules.system_monitor import get_disk_usage_monitor

_logger = logging.getLogger(__name__)

router = RPCRouter()


@router.expose()
@validate_call(config={"arbitrary_types_allowed": True})
async def update_disk_usage(app: FastAPI, *, usage: dict[str, DiskUsage]) -> None:
    disk_usage_monitor = get_disk_usage_monitor(app)

    if disk_usage_monitor is None:
        _logger.warning(
            "Disk usage monitor not initialized, could not update disk usage"
        )
        return

    disk_usage_monitor.set_disk_usage_for_path(usage)
