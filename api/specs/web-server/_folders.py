""" Helper script to generate OAS automatically
"""

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from models_library.api_schemas_webserver.folders import (
    CreateFolderBodyParams,
    FolderGet,
    PutFolderBodyParams,
)
from models_library.generics import Envelope
from models_library.rest_pagination import PageQueryParameters
from pydantic import Json
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.folders._folders_handlers import FoldersPathParams
from simcore_service_webserver.folders._groups_api import FolderGroupGet
from simcore_service_webserver.folders._groups_handlers import (
    _FoldersGroupsBodyParams,
    _FoldersGroupsPathParams,
)

router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=[
        "folders",
    ],
)

### Folders


@router.post(
    "/folders",
    response_model=Envelope[FolderGet],
    status_code=status.HTTP_201_CREATED,
)
async def create_folder(_body: CreateFolderBodyParams):
    ...


@router.get(
    "/folders",
    response_model=Envelope[list[FolderGet]],
)
async def list_folders(
    params: Annotated[PageQueryParameters, Depends()],
    order_by: Annotated[
        Json,
        Query(
            description="Order by field (name|description) and direction (asc|desc). The default sorting order is ascending.",
            example='{"field": "name", "direction": "desc"}',
        ),
    ] = '{"field": "name", "direction": "desc"}',
):
    ...


@router.get(
    "/folders/{folder_id}",
    response_model=Envelope[FolderGet],
)
async def get_folder(_path: Annotated[FoldersPathParams, Depends()]):
    ...


@router.put(
    "/folders/{folder_id}",
    response_model=Envelope[FolderGet],
)
async def replace_folder(
    _path: Annotated[FoldersPathParams, Depends()], _body: PutFolderBodyParams
):
    ...


@router.delete(
    "/folders/{folder_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_folder(_path: Annotated[FoldersPathParams, Depends()]):
    ...


### Folders groups


@router.post(
    "/folders/{folder_id}/groups/{group_id}",
    response_model=Envelope[FolderGroupGet],
    status_code=status.HTTP_201_CREATED,
)
async def create_folder_group(
    _path: Annotated[_FoldersGroupsPathParams, Depends()],
    _body: _FoldersGroupsBodyParams,
):
    ...


@router.get(
    "/folders/{folder_id}/groups",
    response_model=Envelope[list[FolderGroupGet]],
)
async def list_folder_groups(_path: Annotated[FoldersPathParams, Depends()]):
    ...


@router.put(
    "/folders/{folder_id}/groups/{group_id}",
    response_model=Envelope[FolderGroupGet],
)
async def replace_folder_group(
    _path: Annotated[_FoldersGroupsPathParams, Depends()],
    _body: _FoldersGroupsBodyParams,
):
    ...


@router.delete(
    "/folders/{folder_id}/groups/{group_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_folder_group(_path: Annotated[_FoldersGroupsPathParams, Depends()]):
    ...
