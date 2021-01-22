import asyncio
from textwrap import dedent
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile, status
from fastapi.exceptions import HTTPException
from fastapi.responses import FileResponse, HTMLResponse

from ..._meta import api_vtag
from ...models.schemas.files import FileMetadata
from ...modules.storage import StorageApi
from ..dependencies.services import get_api_client
from .files_faker import the_fake_impl

router = APIRouter()


## FILES ---------------


@router.get("", response_model=List[FileMetadata])
async def list_files():
    """ Gets metadata for all file resources """
    return the_fake_impl.list_meta()


async def list_files_impl(
    _storage_client: StorageApi = Depends(get_api_client(StorageApi)),
):
    # TODO: pagination
    # TODO: this is just a ping with retries
    # TODO: extend :search see https://cloud.google.com/apis/design/custom_methods
    # await storage_client.get("/")
    raise NotImplementedError()


@router.post(":upload", response_model=FileMetadata)
async def upload_file(file: UploadFile = File(...)):
    """Uploads a single file to the system

    To upload multiple with one call, see upload_files
    """
    metadata = await the_fake_impl.save(file)
    return metadata


async def upload_single_file_impl(
    file: UploadFile = File(...),
    _storage_client: StorageApi = Depends(get_api_client(StorageApi)),
):
    # TODO: FileResponse automatically computes etag. See how is done

    # TODO: every file uploaded is sent to S3 and a link is returned
    # TODO: every session has a folder. A session is defined by the access token
    #

    # TODO: this is just a ping with retries
    ## await storage_client.get("/")
    raise NotImplementedError()


# TODO: disabled until actual use case is presented
# @router.post(":upload-multiple", response_model=List[FileMetadata])
#
async def _upload_files(files: List[UploadFile] = File(...)):
    """ Uploads multiple files to the system """
    # TODO: idealy we should only have upload_multiple_files but Union[List[UploadFile], File] produces an error in
    # generated openapi.json
    async def save_file(file):
        metadata = await the_fake_impl.save(file)
        return metadata

    uploaded = await asyncio.gather(*[save_file(f) for f in files])
    return uploaded


@router.get("/{file_id}", response_model=FileMetadata)
async def get_file(file_id: UUID):
    """ Gets metadata for a given file resource """
    try:
        return the_fake_impl.files[file_id]
    except KeyError as err:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=f"File with identifier {file_id} not found",
        ) from err


@router.post("/{file_id}:download")
async def download_file(file_id: UUID):
    # TODO: hash or UUID? Ideally like container ids
    try:
        metadata = the_fake_impl.files[file_id]
        file_path = the_fake_impl.get_storage_path(metadata)

        return FileResponse(
            str(file_path),
            media_type=metadata.content_type,
            filename=metadata.filename,
        )
    except KeyError as err:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=f"File with identifier {file_id} not found",
        ) from err


async def files_upload_multiple_view():
    """Extra **Web form** to upload multiple files at http://localhost:8000/v0/files/upload-form-view
        and overcomes the limitations of Swagger-UI view

    NOTE: Only enabled if DEBUG=1
    NOTE: As of 2020-10-07, Swagger UI doesn't support multiple file uploads in the same form field
    """
    return HTMLResponse(
        content=dedent(
            f"""
        <body>
        <form action="/{api_vtag}/files:upload" enctype="multipart/form-data" method="post">
        <input name="files" type="file" multiple>
        <input type="submit">
        </form>
        </body>
        """
        )
    )
