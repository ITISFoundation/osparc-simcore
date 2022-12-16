""" Helper script to generate OAS automatically
"""

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from enum import Enum
from typing import Union

from fastapi import FastAPI, status
from models_library.generics import Envelope
from pydantic import NonNegativeInt
from simcore_service_webserver.storage_schemas import (
    CompleteUpload,
    DatasetMetaData,
    FileLocation,
    FileMetaData,
    FileUploadComplete,
    FileUploadCompleteFuture,
    FileUploadSchema,
    PresignedLink,
    TableSynchronisation,
)

app = FastAPI(redoc_url=None)

TAGS: list[Union[str, Enum]] = [
    "storage",
]


@app.get(
    "/storage/locations",
    response_model=list[FileLocation],
    tags=TAGS,
    operation_id="get_storage_locations",
    summary="Get available storage locations",
)
async def get_storage_locations():
    """Returns the list of available storage locations"""


@app.post(
    "/storage/locations/{location_id}:sync",
    response_model=Envelope[TableSynchronisation],
    tags=TAGS,
    operation_id="synchronise_meta_data_table",
    summary="Manually triggers the synchronisation of the file meta data table in the database",
)
async def synchronise_meta_data_table(
    location_id: str, dry_run: bool = True, fire_and_forget: bool = False
):
    """Returns an object containing added, changed and removed paths"""


@app.get(
    "storage/locations/{location_id}/datasets",
    response_model=Envelope[DatasetMetaData],
    tags=TAGS,
    operation_id="get_datasets_metadata",
    summary="Get datasets metadata",
)
async def get_datasets_metadata(location_id: str):
    """Returns the list of dataset meta-datas"""


@app.get(
    "/storage/locations/{location_id}/files/metadata",
    response_model=list[DatasetMetaData],
    tags=TAGS,
    operation_id="get_files_metadata",
    summary="Get datasets metadata",
)
async def get_files_metadata(location_id: str):
    """list of file meta-datas"""


@app.get(
    "/storage/locations/{location_id}/datasets/{dataset_id}/metadata",
    response_model=list[FileMetaData],
    tags=TAGS,
    operation_id="get_files_metadata_dataset",
    summary="Get Files Metadata",
)
async def get_files_metadata_dataset(location_id: str, dataset_id: str):
    """list of file meta-datas"""


@app.get(
    "/storage/locations/{location_id}/files/{file_id}",
    response_model=PresignedLink,
    tags=TAGS,
    operation_id="download_file",
    summary="Returns download link for requested file",
)
async def download_file(location_id: str, file_id: str):
    """Returns a presigned link"""


@app.put(
    "/storage/locations/{location_id}/files/{file_id}",
    response_model=Envelope[FileUploadSchema],
    tags=TAGS,
    operation_id="upload_file",
    summary="Returns upload link",
)
async def upload_file(location_id: str, file_id: str, file_size: NonNegativeInt):
    """Return upload object"""
    # TODO: links !!!


@app.delete(
    "/storage/locations/{location_id}/files/{file_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=TAGS,
    operation_id="delete_file",
    summary="Deletes File",
)
async def delete_file(location_id: str, file_id: str):
    ...


@app.post(
    "/storage/locations/{location_id}/files/{file_id}:abort",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=TAGS,
    operation_id="abort_upload_file",
)
async def abort_upload_file(location_id: str, file_id: str):
    """Asks the server to abort the upload and revert to the last valid version if any"""


@app.post(
    "/storage/locations/{location_id}/files/{file_id}:complete",
    status_code=status.HTTP_202_ACCEPTED,  # TODO: Completion of upload is accepted
    response_model=Envelope[FileUploadComplete],
    tags=TAGS,
    operation_id="complete_upload_file",
)
async def complete_upload_file(location_id: str, file_id: str, upload: CompleteUpload):
    """Asks the server to complete the upload"""
    # TODO:  links CompleteUploadStatus


@app.post(
    "/storage/locations/{location_id}/files/{file_id}:complete/futures/{future_id}",
    response_model=Envelope[FileUploadCompleteFuture],
    tags=TAGS,
    summary="Check for upload completion",
    operation_id="is_completed_upload_file",
)
async def is_completed_upload_file(location_id: str, file_id: str, future_id: str):
    """Returns state of upload completion"""


@app.get(
    "/storage/locations/{location_id}/files/{file_id}/metadata",
    response_model=FileMetaData,
    tags=TAGS,
    summary="Get File Metadata",
    operation_id="get_file_metadata",
)
async def get_file_metadata(location_id: str, file_id: str):
    ...


if __name__ == "__main__":

    from _common import CURRENT_DIR, create_openapi_specs

    create_openapi_specs(app, CURRENT_DIR.parent / "openapi-storage.ignore.yaml")
