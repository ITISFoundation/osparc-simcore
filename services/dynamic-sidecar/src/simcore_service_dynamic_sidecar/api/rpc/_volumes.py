from fastapi import FastAPI
from models_library.sidecar_volumes import VolumeCategory, VolumeStatus
from pydantic import validate_call
from servicelib.rabbitmq import RPCRouter

from ...services import volumes

router = RPCRouter()


@router.expose()
@validate_call(config={"arbitrary_types_allowed": True})
async def update_volume_status(
    app: FastAPI, *, status: VolumeStatus, category: VolumeCategory
) -> None:
    """Updates the state of the volume"""
    await volumes.update_volume_status(app, status=status, category=category)
