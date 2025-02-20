from fastapi import FastAPI
from models_library.api_schemas_dynamic_sidecar.telemetry import DiskUsage
from pydantic import validate_call
from servicelib.rabbitmq import RPCRouter

from ...modules.system_monitor import get_disk_usage_monitor

router = RPCRouter()


@router.expose()
@validate_call(config={"arbitrary_types_allowed": True})
async def update_disk_usage(app: FastAPI, *, usage: dict[str, DiskUsage]) -> None:
    get_disk_usage_monitor(app).set_disk_usage_for_path(usage)
