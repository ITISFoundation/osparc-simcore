from fastapi import FastAPI
from models_library.sidecar_volumes import VolumeCategory, VolumeStatus
from pydantic import validate_call
from servicelib.rabbitmq import RPCRouter

from ...services import volumes

router = RPCRouter()


@router.expose()
@validate_call(config={"arbitrary_types_allowed": True})
async def save_volume_state(
    app: FastAPI, *, status: VolumeStatus, category: VolumeCategory
) -> None:
    await volumes.save_volume_state(app, status=status, category=category)
