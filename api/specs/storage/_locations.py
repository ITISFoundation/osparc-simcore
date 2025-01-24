from typing import Annotated

from fastapi import APIRouter, Depends
from models_library.api_schemas_storage import FileLocation
from servicelib.aiohttp import status
from simcore_service_storage._meta import API_VTAG
from simcore_service_storage.models import (
    LocationPathParams,
    StorageQueryParamsBase,
    SyncMetadataQueryParams,
)

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
): ...


@router.post("/locations/{location_id}:sync")
async def synchronise_meta_data_table(
    _query: Annotated[SyncMetadataQueryParams, Depends()],
    _path: Annotated[LocationPathParams, Depends()],
):
    ...

    # return web.json_response(
    #     {
    #         "error": None,
    #         "data": {
    #             "removed": sync_results,
    #             "fire_and_forget": query_params.fire_and_forget,
    #             "dry_run": query_params.dry_run,
    #         },
    #     },
    #     dumps=json_dumps,
    # )
