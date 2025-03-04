import logging
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi_pagination import create_page, resolve_params
from models_library.api_schemas_storage.storage_schemas import PathMetaDataGet
from models_library.api_schemas_webserver.storage import LargeLimitedPage
from models_library.users import UserID

from ...dsm_factory import BaseDataManager
from .dependencies.dsm_prodiver import get_data_manager

_logger = logging.getLogger(__name__)

router = APIRouter(
    tags=[
        "files",
    ],
)


@router.get(
    "/locations/{location_id}/paths",
    response_model=LargeLimitedPage[PathMetaDataGet],
)
async def list_paths(
    page_params: Annotated[LargeLimitedPage.__params_type__, Depends()],
    dsm: Annotated[BaseDataManager, Depends(get_data_manager)],
    user_id: UserID,
    file_filter: Path | None = None,
) -> LargeLimitedPage[PathMetaDataGet]:
    """Returns one level of files (paginated)"""
    page_params = resolve_params()
    items, next_cursor, total_number = await dsm.list_paths(
        user_id=user_id,
        file_filter=file_filter,
        limit=page_params.size,
        cursor=page_params.to_raw_params().cursor,
    )
    return create_page(
        [_.to_api_model() for _ in items],
        total=total_number,
        params=page_params,
        next_=next_cursor,
    )
