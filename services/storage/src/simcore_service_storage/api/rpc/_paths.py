import asyncio
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI
from models_library.api_schemas_rpc_async_jobs.async_jobs import (
    AsyncJobGet,
    AsyncJobId,
)
from models_library.projects_nodes_io import LocationID
from models_library.users import UserID
from servicelib.rabbitmq import RPCRouter

from ...dsm import get_dsm_provider

router = RPCRouter()


@router.expose(reraise_if_error_type=())
async def compute_path_size(
    app: FastAPI,
    user_id: UserID,
    location_id: LocationID,
    path: Path,
) -> AsyncJobGet:
    assert app  # nosec

    dsm = get_dsm_provider(app).get(location_id)
    # TODO: this must be send to Celery!
    task = asyncio.create_task(
        dsm.compute_path_size(user_id, path=path), name="THISSHALLGOTOCELERY"
    )
    await asyncio.sleep(5)

    return AsyncJobGet(
        job_id=AsyncJobId(f"{uuid4()}"),
    )
