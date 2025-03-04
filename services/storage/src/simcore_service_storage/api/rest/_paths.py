import logging
from pathlib import Path
from typing import Annotated, TypeVar

from fastapi import APIRouter, Depends, Query
from fastapi_pagination import create_page, resolve_params
from fastapi_pagination.cursor import CursorPage
from fastapi_pagination.customization import CustomizedPage, UseParamsFields
from models_library.api_schemas_storage.storage_schemas import PathMetaDataGet
from models_library.users import UserID

from ...dsm_factory import BaseDataManager
from .dependencies.dsm_prodiver import get_data_manager

_logger = logging.getLogger(__name__)

router = APIRouter(
    tags=[
        "files",
    ],
)

T = TypeVar("T")

Page = CustomizedPage[
    CursorPage[T],
    # Customizes the maximum value to fit frontend needs
    UseParamsFields(
        size=Query(
            50,
            ge=1,
            le=1000,
            description="Page size",
        )
    ),
]


@router.get(
    "/locations/{location_id}/paths",
    response_model=Page[PathMetaDataGet],
)
async def list_paths(
    page_params: Annotated[Page.__params_type__, Depends()],
    dsm: Annotated[BaseDataManager, Depends(get_data_manager)],
    user_id: UserID,
    file_filter: Path | None = None,
) -> Page[PathMetaDataGet]:
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
