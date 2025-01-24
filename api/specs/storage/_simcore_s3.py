from typing import Annotated

from fastapi import APIRouter, Depends, status
from models_library.api_schemas_long_running_tasks.tasks import TaskGet
from models_library.api_schemas_storage import FileMetaDataGet, FoldersBody
from models_library.generics import Envelope
from settings_library.s3 import S3Settings
from simcore_service_storage._meta import API_VTAG
from simcore_service_storage.api.rest.simcore_s3 import (
    DeleteFolderQueryParams,
    SimcoreS3FoldersParams,
)
from simcore_service_storage.models import SearchFilesQueryParams

from api.specs.storage._datasets import StorageQueryParamsBase

router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=[
        "simcore-s3",
    ],
)


@router.post("/simcore-s3:access", response_model=Envelope[S3Settings])
async def get_or_create_temporary_s3_access(
    _query: Annotated[StorageQueryParamsBase, Depends()],
):
    ...


@router.post(
    "/simcore-s3/folders",
    response_model=Envelope[TaskGet],
    status_code=status.HTTP_202_ACCEPTED,
)
async def copy_folders_from_project(
    _query: Annotated[StorageQueryParamsBase, Depends()],
    _body: Annotated[FoldersBody, Depends()],
):
    ...


@router.delete(
    "/simcore-s3/folders/{folder_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_folders_of_project(
    _query: Annotated[DeleteFolderQueryParams, Depends()],
    _path: Annotated[SimcoreS3FoldersParams, Depends()],
):
    ...


@router.post(
    "/simcore-s3/files/metadata:search",
    response_model=Envelope[list[FileMetaDataGet]],
)
async def search_files(
    _query: Annotated[SearchFilesQueryParams, Depends()],
    _path: Annotated[SimcoreS3FoldersParams, Depends()],
):
    ...
