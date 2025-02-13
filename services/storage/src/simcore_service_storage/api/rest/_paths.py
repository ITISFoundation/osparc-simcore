import logging
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi_pagination import LimitOffsetPage, LimitOffsetParams, create_page
from models_library.api_schemas_storage import FileMetaDataGet
from models_library.users import UserID

from ...dsm_factory import BaseDataManager
from .dependencies.dsm_prodiver import get_data_manager

_logger = logging.getLogger(__name__)

router = APIRouter(
    tags=[
        "filesV2",
    ],
)


@router.get(
    "/locations/{location_id}/paths",
    response_model=LimitOffsetPage[FileMetaDataGet],
)
async def list_paths(
    page_params: Annotated[LimitOffsetParams, Depends()],
    dsm: Annotated[BaseDataManager, Depends(get_data_manager)],
    user_id: UserID,
    file_filter: Path | None = None,
):
    """Returns one level of files (paginated)"""
    items, total_number = await dsm.list_files_paginated(
        user_id=user_id,
        file_filter=file_filter,
        limit=page_params.limit,
        offset=page_params.offset,
    )
    return create_page(items, total=total_number, params=page_params)
