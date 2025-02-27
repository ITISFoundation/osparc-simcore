import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from models_library.api_schemas_storage.storage_schemas import FileLocation
from models_library.generics import Envelope

from ...dsm import get_dsm_provider
from ...models import StorageQueryParamsBase

_logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["locations"],
)


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
