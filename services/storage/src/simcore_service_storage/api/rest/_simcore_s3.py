import logging
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request
from models_library.api_schemas_storage.simcore_s3_schemas import S3SettingsGet
from models_library.api_schemas_storage.storage_schemas import (
    FileMetaDataGet,
)
from models_library.generics import Envelope
from models_library.projects import ProjectID
from servicelib.aiohttp import status
from settings_library.s3 import S3Settings

from ...dsm import get_dsm_provider
from ...models import (
    DeleteFolderQueryParams,
    FileMetaData,
    SearchFilesQueryParams,
    StorageQueryParamsBase,
)
from ...modules import sts
from ...simcore_s3_dsm import SimcoreS3DataManager

_logger = logging.getLogger(__name__)

router = APIRouter(
    tags=[
        "simcore-s3",
    ],
)


@router.post("/simcore-s3:access", response_model=Envelope[S3SettingsGet])
async def get_or_create_temporary_s3_access(
    query_params: Annotated[StorageQueryParamsBase, Depends()],
    request: Request,
):
    # NOTE: the name of the method is not accurate, these are not temporary at all
    # it returns the credentials of the s3 backend!
    s3_settings: S3Settings = await sts.get_or_create_temporary_token_for_user(request.app, query_params.user_id)

    # Manually construct the response dict with secrets exposed as plain strings
    response_data = {
        "S3_ACCESS_KEY": s3_settings.S3_ACCESS_KEY.get_secret_value(),
        "S3_SECRET_KEY": s3_settings.S3_SECRET_KEY.get_secret_value(),
        "S3_BUCKET_NAME": s3_settings.S3_BUCKET_NAME,
        "S3_REGION": s3_settings.S3_REGION,
    }
    if s3_settings.S3_ENDPOINT:
        response_data["S3_ENDPOINT"] = str(s3_settings.S3_ENDPOINT)

    # Use model_construct to skip validation and keep secrets as plain strings
    return Envelope.model_construct(data=response_data, error=None)


@router.delete(
    "/simcore-s3/folders/{folder_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_folders_of_project(
    query_params: Annotated[DeleteFolderQueryParams, Depends()],
    folder_id: str,
    request: Request,
):
    dsm = cast(
        SimcoreS3DataManager,
        get_dsm_provider(request.app).get(SimcoreS3DataManager.get_location_id()),
    )
    await dsm.delete_project_simcore_s3(
        query_params.user_id,
        ProjectID(folder_id),
        query_params.node_id,
    )


@router.post(
    "/simcore-s3/files/metadata:search",
    response_model=Envelope[list[FileMetaDataGet]],
)
async def search_files(query_params: Annotated[SearchFilesQueryParams, Depends()], request: Request):
    dsm = cast(
        SimcoreS3DataManager,
        get_dsm_provider(request.app).get(SimcoreS3DataManager.get_location_id()),
    )

    data: list[FileMetaData] = await dsm.search_owned_files(
        user_id=query_params.user_id,
        file_id_prefix=query_params.startswith,
        sha256_checksum=query_params.sha256_checksum,
        limit=query_params.limit,
        offset=query_params.offset,
    )
    _logger.debug(
        "Found %d files starting with '%s'",
        len(data),
        f"{query_params.startswith=}, {query_params.sha256_checksum=}",
    )
    return Envelope[list[FileMetaDataGet]](data=[FileMetaDataGet(**d.model_dump()) for d in data])
