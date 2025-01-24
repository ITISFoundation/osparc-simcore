from typing import Annotated

from fastapi import APIRouter, Depends, status
from models_library.api_schemas_storage import (
    FileMetaDataGet,
    FileUploadCompleteFutureResponse,
    FileUploadCompleteResponse,
    FileUploadCompletionBody,
    FileUploadSchema,
    SoftCopyBody,
)
from models_library.generics import Envelope
from simcore_service_storage._meta import API_VTAG
from simcore_service_storage.models import (
    CopyAsSoftLinkParams,
    FileDownloadQueryParams,
    FileDownloadResponse,
    FileMetadataListQueryParams,
    FilePathIsUploadCompletedParams,
    FilePathParams,
    FileUploadQueryParams,
    FileUploadResponseV1,
)

from api.specs.storage._datasets import LocationPathParams, StorageQueryParamsBase

router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=[
        "files",
    ],
)


@router.get(
    "/locations/{location_id}/files/metadata",
    response_model=Envelope[list[FileMetaDataGet]],
)
async def list_files_metadata(
    _query: Annotated[FileMetadataListQueryParams, Depends()],
    _path: Annotated[LocationPathParams, Depends()],
):
    ...


@router.get(
    "/locations/{location_id}/files/{file_id}/metadata",
    response_model=Envelope[FileMetaDataGet],
)
async def get_file_metadata(
    _query: Annotated[StorageQueryParamsBase, Depends()],
    _path: Annotated[FilePathParams, Depends()],
):
    ...


@router.get(
    "/locations/{location_id}/files/{file_id}",
    response_model=Envelope[FileDownloadResponse],
)
async def download_file(
    _query: Annotated[FileDownloadQueryParams, Depends()],
    _path: Annotated[FilePathParams, Depends()],
):
    ...


@router.put(
    "/locations/{location_id}/files/{file_id}",
    response_model=Envelope[FileUploadResponseV1] | FileUploadSchema,
)
async def upload_file(
    _query: Annotated[FileUploadQueryParams, Depends()],
    _path: Annotated[FilePathParams, Depends()],
):
    ...


@router.post(
    "/locations/{location_id}/files/{file_id}:abort",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def abort_upload_file(
    _query: Annotated[StorageQueryParamsBase, Depends()],
    _path: Annotated[FilePathParams, Depends()],
):
    ...


@router.post(
    "/locations/{location_id}/files/{file_id}:complete",
    reponse_model=Envelope[FileUploadCompleteResponse],
)
async def complete_upload_file(
    _query: Annotated[StorageQueryParamsBase, Depends()],
    _path: Annotated[FilePathParams, Depends()],
    _body: Annotated[FileUploadCompletionBody, Depends()],
):
    ...


@router.post(
    "/locations/{location_id}/files/{file_id}:complete/futures/{future_id}",
    response_model=FileUploadCompleteFutureResponse,
    reponses={status.HTTP_404_NOT_FOUND},
)
async def is_completed_upload_file(
    _query: Annotated[StorageQueryParamsBase, Depends()],
    _path: Annotated[FilePathIsUploadCompletedParams, Depends()],
):
    ...


@router.delete(
    "/locations/{location_id}/files/{file_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_file(
    _query: Annotated[StorageQueryParamsBase, Depends()],
    _path: Annotated[FilePathIsUploadCompletedParams, Depends()],
):
    ...


@router.post("/files/{file_id}:soft-copy", response_model=FileMetaDataGet)
async def copy_as_soft_link(
    _query: Annotated[StorageQueryParamsBase, Depends()],
    _path: Annotated[CopyAsSoftLinkParams, Depends()],
    _body: Annotated[SoftCopyBody, Depends()],
):
    ...
