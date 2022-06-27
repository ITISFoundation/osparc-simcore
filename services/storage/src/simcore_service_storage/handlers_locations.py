import asyncio
import logging

from aiohttp import web
from aiohttp.web import RouteTableDef
from models_library.projects_nodes_io import StorageFileID
from models_library.utils.fastapi_encoders import jsonable_encoder
from servicelib.aiohttp.application_keys import (
    APP_CONFIG_KEY,
    APP_FIRE_AND_FORGET_TASKS_KEY,
)
from servicelib.aiohttp.requests_validation import (
    parse_request_path_parameters_as,
    parse_request_query_parameters_as,
)
from servicelib.utils import fire_and_forget_task

# Exclusive for simcore-s3 storage -----------------------
from ._meta import api_vtag
from .models import LocationPathParams, StorageQueryParamsBase, SyncMetadataQueryParams
from .settings import Settings
from .utils import get_location_from_id
from .utils_handlers import prepare_storage_manager

log = logging.getLogger(__name__)

routes = RouteTableDef()


# HANDLERS ---------------------------------------------------
@routes.get(f"/{api_vtag}/locations", name="get_storage_locations")  # type: ignore
async def get_storage_locations(request: web.Request):
    query_params = parse_request_query_parameters_as(StorageQueryParamsBase, request)
    log.debug(
        "received call to get_storage_locations with %s",
        f"{query_params=}",
    )

    dsm = await prepare_storage_manager({}, jsonable_encoder(query_params), request)
    locs = await dsm.locations(query_params.user_id)

    return {"error": None, "data": locs}


@routes.post(f"/{api_vtag}/locations/{{location_id}}:sync", name="synchronise_meta_data_table")  # type: ignore
async def synchronise_meta_data_table(request: web.Request):
    query_params = parse_request_query_parameters_as(SyncMetadataQueryParams, request)
    path_params = parse_request_path_parameters_as(LocationPathParams, request)
    log.debug(
        "received call to synchronise_meta_data_table with %s",
        f"{path_params=}, {query_params=}",
    )

    dsm = await prepare_storage_manager(
        jsonable_encoder(path_params), jsonable_encoder(query_params), request
    )
    sync_results: list[StorageFileID] = []
    sync_coro = dsm.synchronise_meta_data_table(
        get_location_from_id(path_params.location_id), query_params.dry_run
    )

    if query_params.fire_and_forget:
        settings: Settings = request.app[APP_CONFIG_KEY]

        async def _go():
            timeout = settings.STORAGE_SYNC_METADATA_TIMEOUT
            try:
                result = await asyncio.wait_for(sync_coro, timeout=timeout)
                log.info(
                    "Sync metadata table completed: %d entries removed",
                    len(result),
                )
            except asyncio.TimeoutError:
                log.error("Sync metadata table timed out (%s seconds)", timeout)

        fire_and_forget_task(
            _go(),
            task_suffix_name="synchronise_meta_data_table",
            fire_and_forget_tasks_collection=request.app[APP_FIRE_AND_FORGET_TASKS_KEY],
        )
    else:
        sync_results = await sync_coro

    return {
        "error": None,
        "data": {
            "removed": sync_results,
            "fire_and_forget": query_params.fire_and_forget,
            "dry_run": query_params.dry_run,
        },
    }
