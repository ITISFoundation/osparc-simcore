import asyncio
import hashlib
from textwrap import dedent
from typing import List

from fastapi import APIRouter, Depends, File, UploadFile, status
from fastapi.exceptions import HTTPException
from fastapi.responses import FileResponse, HTMLResponse

from ..._meta import api_vtag
from ...models.schemas.files import FileUploaded
from ...modules.storage import StorageApi
from ..dependencies.services import get_api_client
from .files_faker import FAKE

router = APIRouter()


@router.get("")
async def list_files(
    _storage_client: StorageApi = Depends(get_api_client(StorageApi)),
):
    """ Lists all user's files """
    # TODO: this is just a ping with retries
    # await storage_client.get("/")

    # TODO: pagination
    # raise NotImplementedError()
    return [metadata for metadata, _ in FAKE.files]


@router.post(":upload", response_model=FileUploaded)
async def upload_single_file(
    file: UploadFile = File(...),
    _storage_client: StorageApi = Depends(get_api_client(StorageApi)),
):
    # TODO: every file uploaded is sent to S3 and a link is returned
    # TODO: every session has a folder. A session is defined by the access token
    #

    # TODO: this is just a ping with retries
    ## await storage_client.get("/")

    metadata = FileUploaded(
        filename=file.filename,
        content_type=file.content_type,
        hash=await eval_sha256_hash(file),
        # TODO: FileResponse automatically computes etag. See how is done
    )

    await FAKE.save(metadata, file)
    return metadata


@router.post(":upload-multiple", response_model=List[FileUploaded])
async def upload_multiple_files(files: List[UploadFile] = File(...)):
    # TODO: every file uploaded is sent to S3 and a link is returned
    # TODO: every session has a folder. A session is defined by the access token
    #
    async def go(file):
        metadata = FileUploaded(
            filename=file.filename,
            content_type=file.content_type,
            hash=await eval_sha256_hash(file),
        )
        await FAKE.save(metadata, file)
        return metadata

    uploaded = await asyncio.gather(*[go(f) for f in files])
    return uploaded


@router.get("/{file_id}:download")
async def download_file(file_id: str):
    # TODO: hash or UUID? Ideally like container ids
    try:
        metadata, file_path = await FAKE.get(file_id)
    except KeyError as err:
        raise HTTPException(status.HTTP_404_NOT_FOUND) from err

    return FileResponse(
        str(file_path),
        media_type=metadata.content_type,
        filename=metadata.filename,
    )


### HELPERS ------------------------------


@router.get("/upload-multiple-view")
async def files_upload_multiple_view():
    """Web form to upload files at http://localhost:8000/v0/files/upload-form-view

    Overcomes limitation of Swagger UI view
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


async def eval_sha256_hash(file: UploadFile):
    # TODO: adaptive chunks depending on file size
    # SEE: https://stackoverflow.com/questions/17731660/hashlib-optimal-size-of-chunks-to-be-used-in-md5-update

    sha256_hash = hashlib.sha256()
    CHUNK_BYTES = 4 * 1024  # 4K blocks

    while True:
        await file.seek(0)
        chunk = await file.read(CHUNK_BYTES)
        if not chunk:
            break
        sha256_hash.update(chunk)
    return sha256_hash.hexdigest()
