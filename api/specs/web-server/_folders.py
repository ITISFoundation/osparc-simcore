""" Helper script to generate OAS automatically
"""

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from typing import Annotated

from _common import as_query
from fastapi import APIRouter, Depends, status
from models_library.api_schemas_webserver.folders_v2 import (
    CreateFolderBodyParams,
    FolderGet,
    PutFolderBodyParams,
)
from models_library.generics import Envelope
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.folders._models import (
    FolderSearchQueryParams,
    FoldersListQueryParams,
    FoldersPathParams,
)

router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=[
        "folders",
    ],
)


@router.post(
    "/folders",
    response_model=Envelope[FolderGet],
    status_code=status.HTTP_201_CREATED,
)
async def create_folder(
    _b: CreateFolderBodyParams,
):
    ...


@router.get(
    "/folders",
    response_model=Envelope[list[FolderGet]],
)
async def list_folders(
    _q: Annotated[as_query(FoldersListQueryParams), Depends()],
):
    ...


@router.get(
    "/folders:search",
    response_model=Envelope[list[FolderGet]],
)
async def list_folders_full_search(
    _q: Annotated[as_query(FolderSearchQueryParams), Depends()],
):
    ...


@router.get(
    "/folders/{folder_id}",
    response_model=Envelope[FolderGet],
)
async def get_folder(
    _p: Annotated[FoldersPathParams, Depends()],
):
    ...


@router.put(
    "/folders/{folder_id}",
    response_model=Envelope[FolderGet],
)
async def replace_folder(
    _p: Annotated[FoldersPathParams, Depends()],
    _b: PutFolderBodyParams,
):
    ...


@router.delete(
    "/folders/{folder_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_folder(
    _p: Annotated[FoldersPathParams, Depends()],
):
    ...
