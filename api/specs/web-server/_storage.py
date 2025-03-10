# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from typing import Annotated, TypeAlias
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from models_library.api_schemas_storage.storage_schemas import (
    FileLocation,
    FileMetaDataGet,
    FileUploadCompleteFutureResponse,
    FileUploadCompleteResponse,
    FileUploadCompletionBody,
    FileUploadSchema,
    LinkType,
    PathMetaDataGet,
    PresignedLink,
)
from models_library.api_schemas_webserver.storage import (
    DataExportPost,
    ListPathsQueryParams,
    StorageAsyncJobGet,
    StorageAsyncJobResult,
    StorageAsyncJobStatus,
    StorageLocationPathParams,
)
from models_library.generics import Envelope
from models_library.projects_nodes_io import LocationID
from models_library.users import UserID
from pydantic import AnyUrl, ByteSize
from servicelib.fastapi.rest_pagination import CustomizedPathsCursorPage
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.storage.schemas import DatasetMetaData, FileMetaData

router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=["storage"],
)


# NOTE: storage generates URLs that contain double encoded
# slashes, and when applying validation via `StorageFileID`
# it raises an error. Before `StorageFileID`, `str` was the
# type used in the OpenAPI specs.
StorageFileIDStr: TypeAlias = str


@router.get(
    "/storage/locations",
    response_model=list[FileLocation],
    description="Get available storage locations",
)
async def list_storage_locations():
    """Returns the list of available storage locations"""


@router.get(
    "/storage/locations/{location_id}/paths",
    response_model=CustomizedPathsCursorPage[PathMetaDataGet],
)
async def list_storage_paths(
    _path: Annotated[StorageLocationPathParams, Depends()],
    _query: Annotated[ListPathsQueryParams, Depends()],
):
    """Lists the files/directories in WorkingDirectory"""


@router.get(
    "/storage/locations/{location_id}/datasets",
    response_model=Envelope[list[DatasetMetaData]],
    description="Get datasets metadata",
)
async def list_datasets_metadata(
    _path: Annotated[StorageLocationPathParams, Depends()],
):
    """returns all the top level datasets a user has access to"""


@router.get(
    "/storage/locations/{location_id}/files/metadata",
    response_model=Envelope[list[DatasetMetaData]],
    description="Get datasets metadata",
)
async def get_files_metadata(
    _path: Annotated[StorageLocationPathParams, Depends()],
    uuid_filter: str = "",
    expand_dirs: bool = Query(
        True,
        description=(
            "Automatic directory expansion. This will be replaced by pagination the future"
        ),
    ),
):
    """returns all the file meta data a user has access to (uuid_filter may be used)"""


@router.get(
    "/storage/locations/{location_id}/datasets/{dataset_id}/metadata",
    response_model=Envelope[list[FileMetaDataGet]],
    description="Get Files Metadata",
)
async def list_dataset_files_metadata(
    location_id: LocationID,
    dataset_id: str,
    expand_dirs: bool = Query(
        True,
        description=(
            "Automatic directory expansion. This will be replaced by pagination the future"
        ),
    ),
):
    """returns all the file meta data inside dataset with dataset_id"""


@router.get(
    "/storage/locations/{location_id}/files/{file_id}/metadata",
    response_model=FileMetaData | Envelope[FileMetaDataGet],
    description="Get File Metadata",
)
async def get_file_metadata(location_id: LocationID, file_id: StorageFileIDStr):
    """returns the file meta data of file_id if user_id has the rights to"""


@router.get(
    "/storage/locations/{location_id}/files/{file_id}",
    response_model=Envelope[PresignedLink],
    description="Returns download link for requested file",
)
async def download_file(
    location_id: LocationID,
    file_id: StorageFileIDStr,
    link_type: LinkType = LinkType.PRESIGNED,
):
    """creates a download file link if user has the rights to"""


@router.put(
    "/storage/locations/{location_id}/files/{file_id}",
    response_model=Envelope[FileUploadSchema] | Envelope[AnyUrl],
    description="Returns upload link",
)
async def upload_file(
    location_id: LocationID,
    file_id: StorageFileIDStr,
    file_size: ByteSize | None,
    link_type: LinkType = LinkType.PRESIGNED,
    is_directory: bool = False,
):
    """creates one or more upload file links if user has the rights to, expects the client to complete/abort upload"""


@router.delete(
    "/storage/locations/{location_id}/files/{file_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    description="Deletes File",
)
async def delete_file(location_id: LocationID, file_id: StorageFileIDStr):
    """deletes file if user has the rights to"""


@router.post(
    "/storage/locations/{location_id}/files/{file_id}:abort",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def abort_upload_file(location_id: LocationID, file_id: StorageFileIDStr):
    """aborts an upload if user has the rights to, and reverts
    to the latest version if available, else will delete the file"""


@router.post(
    "/storage/locations/{location_id}/files/{file_id}:complete",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=Envelope[FileUploadCompleteResponse],
)
async def complete_upload_file(
    body_item: Envelope[FileUploadCompletionBody],
    location_id: LocationID,
    file_id: StorageFileIDStr,
):
    """completes an upload if the user has the rights to"""


@router.post(
    "/storage/locations/{location_id}/files/{file_id}:complete/futures/{future_id}",
    response_model=Envelope[FileUploadCompleteFutureResponse],
    description="Check for upload completion",
)
async def is_completed_upload_file(
    location_id: LocationID, file_id: StorageFileIDStr, future_id: str
):
    """Returns state of upload completion"""


# data export
@router.post(
    "/storage/locations/{location_id}/export-data",
    response_model=Envelope[StorageAsyncJobGet],
    name="export_data",
    description="Export data",
)
async def export_data(data_export: DataExportPost, location_id: LocationID):
    """Trigger data export. Returns async job id for getting status and results"""


@router.get(
    "/storage/async-jobs/{job_id}/status",
    response_model=Envelope[StorageAsyncJobStatus],
    name="get_async_job_status",
)
async def get_async_job_status(storage_async_job_get: StorageAsyncJobGet, job_id: UUID):
    """Get async job status"""


@router.post(
    "/storage/async-jobs/{job_id}:abort",
    name="abort_async_job",
)
async def abort_async_job(storage_async_job_get: StorageAsyncJobGet, job_id: UUID):
    """aborts execution of an async job"""


@router.get(
    "/storage/async-jobs/{job_id}/result",
    response_model=Envelope[StorageAsyncJobResult],
    name="get_async_job_result",
)
async def get_async_job_result(storage_async_job_get: StorageAsyncJobGet, job_id: UUID):
    """Get the result of the async job"""


@router.get(
    "/storage/async-jobs",
    response_model=Envelope[list[StorageAsyncJobGet]],
    name="get_async_jobs",
)
async def get_async_jobs(user_id: UserID):
    """Retrunsa list of async jobs for the user"""
