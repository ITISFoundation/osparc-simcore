import asyncio
import logging
from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, Request
from models_library.api_schemas_storage import FileLocation
from models_library.generics import Envelope
from models_library.projects_nodes_io import StorageFileID
from servicelib.aiohttp import status
from servicelib.aiohttp.application_keys import (
    APP_CONFIG_KEY,
    APP_FIRE_AND_FORGET_TASKS_KEY,
)
from servicelib.utils import fire_and_forget_task

# Exclusive for simcore-s3 storage -----------------------
from ...core.settings import ApplicationSettings
from ...dsm import get_dsm_provider
from ...models import (
    LocationID,
    StorageQueryParamsBase,
    SyncMetadataQueryParams,
    SyncMetadataResponse,
)
from ...simcore_s3_dsm import SimcoreS3DataManager

_logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["locations"],
)


# HANDLERS ---------------------------------------------------
@router.get(
    "/locations",
    status_code=status.HTTP_200_OK,
    response_model=Envelope[list[FileLocation]],
)
async def list_storage_locations(
    query_params: Annotated[StorageQueryParamsBase, Depends()], request: Request
):
    dsm_provider = get_dsm_provider(request.app)
    location_ids = dsm_provider.locations()
    locs: list[FileLocation] = []
    for loc_id in location_ids:
        dsm = dsm_provider.get(loc_id)
        if await dsm.authorized(query_params.user_id):
            locs.append(FileLocation(name=dsm.location_name, id=dsm.location_id))
    return Envelope[list[FileLocation]](data=locs)


@router.post(
    "/locations/{location_id}:sync", response_model=Envelope[SyncMetadataResponse]
)
async def synchronise_meta_data_table(
    query_params: Annotated[SyncMetadataQueryParams, Depends()],
    location_id: LocationID,
    request: Request,
):
    if not location_id == SimcoreS3DataManager.get_location_id():
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="invalid call: cannot be called for other than simcore",
        )
    dsm = cast(
        SimcoreS3DataManager,
        get_dsm_provider(request.app).get(SimcoreS3DataManager.get_location_id()),
    )
    sync_results: list[StorageFileID] = []
    sync_coro = dsm.synchronise_meta_data_table(dry_run=query_params.dry_run)

    if query_params.fire_and_forget:
        settings: ApplicationSettings = request.app[APP_CONFIG_KEY]

        async def _go():
            timeout = settings.STORAGE_SYNC_METADATA_TIMEOUT
            try:
                result = await asyncio.wait_for(sync_coro, timeout=timeout)
                _logger.info(
                    "Sync metadata table completed: %d entries removed",
                    len(result),
                )
            except TimeoutError:
                _logger.exception("Sync metadata table timed out (%s seconds)", timeout)

        fire_and_forget_task(
            _go(),
            task_suffix_name="synchronise_meta_data_table",
            fire_and_forget_tasks_collection=request.app[APP_FIRE_AND_FORGET_TASKS_KEY],
        )
    else:
        sync_results = await sync_coro
    response = SyncMetadataResponse(
        removed=sync_results,
        fire_and_forget=query_params.fire_and_forget,
        dry_run=query_params.dry_run,
    )
    return Envelope[SyncMetadataResponse](data=response)
