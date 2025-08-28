from fastapi import FastAPI
from models_library.sidecar_volumes import VolumeCategory, VolumeState, VolumeStatus

from ..models.shared_store import get_shared_store


async def update_volume_status(
    app: FastAPI, *, status: VolumeStatus, category: VolumeCategory
) -> None:
    shared_store = get_shared_store(app)
    async with shared_store:
        shared_store.volume_states[category] = VolumeState(status=status)
