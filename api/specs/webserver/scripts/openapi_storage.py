""" Helper script to generate OAS automatically
"""

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from typing import TypeAlias

from fastapi import APIRouter, FastAPI, Query, status
from models_library.api_schemas_storage import (
    FileMetaDataGet,
    FileUploadCompleteFutureResponse,
    FileUploadCompleteResponse,
    FileUploadCompletionBody,
    FileUploadSchema,
    LinkType,
    PresignedLink,
    TableSynchronisation,
)
from models_library.generics import Envelope
from models_library.projects_nodes_io import LocationID
from pydantic import AnyUrl, ByteSize
from simcore_service_webserver.storage.schemas import DatasetMetaData, FileMetaData

router = APIRouter(tags=["storage"])


# NOTE: storage generates URLs that contain double encoded
# slashes, and when applying validation via `StorageFileID`
# it raises an error. Before `StorageFileID`, `str` was the
# type used in the OpenAPI specs.
StorageFileIDStr: TypeAlias = str


@router.get(
    "/storage/locations",
    response_model=list[DatasetMetaData],
    operation_id="get_storage_locations",
    summary="Get available storage locations",
)
async def get_storage_locations():
    """Returns the list of available storage locations"""


@router.post(
    "/storage/locations/{location_id}:sync",
    response_model=Envelope[TableSynchronisation],
    operation_id="synchronise_meta_data_table",
    summary="Manually triggers the synchronisation of the file meta data table in the database",
)
async def synchronise_meta_data_table(
    location_id: LocationID, dry_run: bool = False, fire_and_forget: bool = False
):
    """Returns an object containing added, changed and removed paths"""


@router.get(
    "/storage/locations/{location_id}/datasets",
    response_model=Envelope[list[DatasetMetaData]],
    operation_id="get_datasets_metadata",
    summary="Get datasets metadata",
)
async def get_datasets_metadata(location_id: LocationID):
    """returns all the top level datasets a user has access to"""


@router.get(
    "/storage/locations/{location_id}/files/metadata",
    response_model=Envelope[list[DatasetMetaData]],
    operation_id="get_files_metadata",
    summary="Get datasets metadata",
)
async def get_files_metadata(
    location_id: LocationID,
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
    operation_id="get_files_metadata_dataset",
    summary="Get Files Metadata",
)
async def get_files_metadata_dataset(
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
    summary="Get File Metadata",
    operation_id="get_file_metadata",
)
async def get_file_metadata(location_id: LocationID, file_id: StorageFileIDStr):
    """returns the file meta data of file_id if user_id has the rights to"""


@router.get(
    "/storage/locations/{location_id}/files/{file_id}",
    response_model=Envelope[PresignedLink],
    operation_id="download_file",
    summary="Returns download link for requested file",
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
    operation_id="upload_file",
    summary="Returns upload link",
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
    operation_id="delete_file",
    summary="Deletes File",
)
async def delete_file(location_id: LocationID, file_id: StorageFileIDStr):
    """deletes file if user has the rights to"""


@router.post(
    "/storage/locations/{location_id}/files/{file_id}:abort",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="abort_upload_file",
)
async def abort_upload_file(location_id: LocationID, file_id: StorageFileIDStr):
    """aborts an upload if user has the rights to, and reverts
    to the latest version if available, else will delete the file"""


@router.post(
    "/storage/locations/{location_id}/files/{file_id}:complete",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=Envelope[FileUploadCompleteResponse],
    operation_id="complete_upload_file",
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
    summary="Check for upload completion",
    operation_id="is_completed_upload_file",
)
async def is_completed_upload_file(
    location_id: LocationID, file_id: StorageFileIDStr, future_id: str
):
    """Returns state of upload completion"""


if __name__ == "__main__":
    from _common import CURRENT_DIR, create_and_save_openapi_specs

    create_and_save_openapi_specs(
        FastAPI(routes=router.routes), CURRENT_DIR.parent / "openapi-storage.yaml"
    )
