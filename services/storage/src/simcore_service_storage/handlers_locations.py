import asyncio
import logging
from typing import cast

from aiohttp import web
from aiohttp.web import RouteTableDef
from common_library.json_serialization import json_dumps
from models_library.api_schemas_storage import FileLocation
from models_library.projects_nodes_io import StorageFileID
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
from ._meta import API_VTAG
from .dsm import get_dsm_provider
from .models import LocationPathParams, StorageQueryParamsBase, SyncMetadataQueryParams
from .settings import Settings
from .simcore_s3_dsm import SimcoreS3DataManager

log = logging.getLogger(__name__)

routes = RouteTableDef()


# HANDLERS ---------------------------------------------------
@routes.get(f"/{API_VTAG}/locations", name="get_storage_locations")
async def get_storage_locations(request: web.Request) -> web.Response:
    query_params: StorageQueryParamsBase = parse_request_query_parameters_as(
        StorageQueryParamsBase, request
    )
    log.debug(
        "received call to get_storage_locations with %s",
        f"{query_params=}",
    )
    dsm_provider = get_dsm_provider(request.app)
    location_ids = dsm_provider.locations()
    locs: list[FileLocation] = []
    for loc_id in location_ids:
        dsm = dsm_provider.get(loc_id)
        if await dsm.authorized(query_params.user_id):
            locs.append(FileLocation(name=dsm.location_name, id=dsm.location_id))

    return web.json_response({"error": None, "data": locs}, dumps=json_dumps)


@routes.post(
    f"/{API_VTAG}/locations/{{location_id}}:sync", name="synchronise_meta_data_table"
)
async def synchronise_meta_data_table(request: web.Request) -> web.Response:
    query_params: SyncMetadataQueryParams = parse_request_query_parameters_as(
        SyncMetadataQueryParams, request
    )
    path_params = parse_request_path_parameters_as(LocationPathParams, request)
    log.debug(
        "received call to synchronise_meta_data_table with %s",
        f"{path_params=}, {query_params=}",
    )

    dsm = cast(
        SimcoreS3DataManager,
        get_dsm_provider(request.app).get(SimcoreS3DataManager.get_location_id()),
    )
    sync_results: list[StorageFileID] = []
    sync_coro = dsm.synchronise_meta_data_table(dry_run=query_params.dry_run)

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
                log.exception("Sync metadata table timed out (%s seconds)", timeout)

        fire_and_forget_task(
            _go(),
            task_suffix_name="synchronise_meta_data_table",
            fire_and_forget_tasks_collection=request.app[APP_FIRE_AND_FORGET_TASKS_KEY],
        )
    else:
        sync_results = await sync_coro

    return web.json_response(
        {
            "error": None,
            "data": {
                "removed": sync_results,
                "fire_and_forget": query_params.fire_and_forget,
                "dry_run": query_params.dry_run,
            },
        },
        dumps=json_dumps,
    )
