""" Helper script to generate OAS automatically
"""

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from models_library.api_schemas_webserver.folders_v2 import (
    CreateFolderBodyParams,
    FolderGet,
    PutFolderBodyParams,
)
from models_library.folders import FolderID
from models_library.generics import Envelope
from models_library.rest_base import RequestParameters
from models_library.rest_pagination import PageQueryParameters
from models_library.workspaces import WorkspaceID
from pydantic import Json
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.folders._models import (
    FolderFilters,
    FolderOrderQueryParamsOpenApi,
    FoldersPathParams,
)


class _ListExtraQueryParams(RequestParameters):
    workspace_id: WorkspaceID | None = None
    folder_id: FolderID | None = None


class _FiltersQueryParams(RequestParameters):
    filters: Annotated[
        Json | None,
        Query(description=FolderFilters.schema_json(indent=1)),
    ] = None


class _ListQueryParams(  # type: ignore
    FolderOrderQueryParamsOpenApi,
    _FiltersQueryParams,
    PageQueryParameters,
    _ListExtraQueryParams,
):
    ...


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
async def create_folder(_b: CreateFolderBodyParams):
    ...


@router.get(
    "/folders",
    response_model=Envelope[list[FolderGet]],
)
async def list_folders(
    _q: Annotated[_ListQueryParams, Depends()],
):
    ...


@router.get(
    "/folders:search",
    response_model=Envelope[list[FolderGet]],
)
async def list_folders_full_search(
    params: Annotated[PageQueryParameters, Depends()],
    text: str | None = None,
    order_by: Annotated[
        Json,
        Query(
            description="Order by field (modified_at|name|description) and direction (asc|desc). The default sorting order is ascending.",
            example='{"field": "name", "direction": "desc"}',
        ),
    ] = '{"field": "modified_at", "direction": "desc"}',
    filters: Annotated[
        Json | None,
        Query(description=FolderFilters.schema_json(indent=1)),
    ] = None,
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
