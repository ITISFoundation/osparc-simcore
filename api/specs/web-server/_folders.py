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
    PutFolderBodyParams,
)
from models_library.api_schemas_webserver.wallets import WalletGet
from models_library.folders import FolderID
from models_library.generics import Envelope
from models_library.rest_pagination import PageQueryParameters
from models_library.users import GroupID
from pydantic import Json
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.folders._groups_api import FolderGroupGet
from simcore_service_webserver.folders._groups_handlers import _FoldersGroupsBodyParams

router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=[
        "folders",
    ],
)

### Folders


@router.post(
    "/folders",
    response_model=Envelope[WalletGet],
    status_code=status.HTTP_201_CREATED,
)
async def create_folder(body: CreateFolderBodyParams):
    ...


@router.get(
    "/folders",
    response_model=Envelope[list[WalletGet]],
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
    response_model=Envelope[WalletGet],
)
async def get_folder(folder_id: FolderID):
    ...


@router.put(
    "/folders/{folder_id}",
    response_model=Envelope[WalletGet],
)
async def replace_folder(folder_id: FolderID, body: PutFolderBodyParams):
    ...


@router.delete(
    "/folders/{folder_id}",
    response_model=Envelope[WalletGet],
)
async def delete_folder(folder_id: FolderID):
    ...


### Folders groups


@router.post(
    "/folders/{folder_id}/groups/{group_id}",
    response_model=Envelope[FolderGroupGet],
    status_code=status.HTTP_201_CREATED,
)
async def create_folder_group(
    folder_id: FolderID, group_id: GroupID, body: _FoldersGroupsBodyParams
):
    ...


@router.get(
    "/folders/{folder_id}/groups",
    response_model=Envelope[list[FolderGroupGet]],
)
async def list_folder_groups(folder_id: FolderID):
    ...


@router.put(
    "/folders/{folder_id}/groups/{group_id}",
    response_model=Envelope[FolderGroupGet],
)
async def replace_folder_group(
    folder_id: FolderID, group_id: GroupID, body: _FoldersGroupsBodyParams
):
    ...


@router.delete(
    "/folders/{folder_id}/groups/{group_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_folder_group(folder_id: FolderID, group_id: GroupID):
    ...
