from typing import Annotated

from fastapi import APIRouter, Depends
from models_library.api_schemas_storage import FileLocation
from servicelib.aiohttp import status
from simcore_service_storage._meta import API_VTAG
from simcore_service_storage.models import StorageQueryParamsBase

router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=["locations"],
)


# HANDLERS ---------------------------------------------------
@router.get(
    "/locations", status_code=status.HTTP_200_OK, response_model=list[FileLocation]
)
async def list_storage_locations(
    _query: Annotated[StorageQueryParamsBase, Depends()],
):
    ...


@routes.post(
    f"/{API_VTAG}/locations/{{location_id}}:sync", name="synchronise_meta_data_table"
)
async def synchronise_meta_data_table(request: web.Request) -> web.Response:
    query_params: SyncMetadataQueryParams = parse_request_query_parameters_as(
        SyncMetadataQueryParams, request
    )
    path_params = parse_request_path_parameters_as(LocationPathParams, request)
    _logger.debug(
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
