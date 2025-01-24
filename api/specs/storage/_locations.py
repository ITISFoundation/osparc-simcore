from typing import Annotated

from fastapi import APIRouter, Depends
from models_library.api_schemas_storage import FileLocation
from servicelib.aiohttp import status
from simcore_service_storage._meta import API_VTAG
from simcore_service_storage.models import (
    LocationPathParams,
    StorageQueryParamsBase,
    SyncMetadataQueryParams,
    SyncMetadataResponse,
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


@router.post("/locations/{location_id}:sync", response_model=SyncMetadataResponse)
async def synchronise_meta_data_table(
    _query: Annotated[SyncMetadataQueryParams, Depends()],
    _path: Annotated[LocationPathParams, Depends()],
): ...
