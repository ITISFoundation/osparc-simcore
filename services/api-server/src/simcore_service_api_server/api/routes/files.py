import asyncio
import hashlib
import sys
from pathlib import Path
from textwrap import dedent
from typing import List
from uuid import UUID

from fastapi import APIRouter, File, UploadFile, Depends
from fastapi.responses import FileResponse, HTMLResponse

from ..._meta import api_vtag
from ...models.schemas.files import FileUploaded
from ...modules.storage import StorageApi
from ..dependencies.services import get_api_client

current_file = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve()

router = APIRouter()


@router.get("")
async def list_files(
        storage_client: StorageApi = Depends(get_api_client(StorageApi)),
    ):
    """ Lists all user's files """
    # TODO: this is just a ping with retries
    await storage_client.get("/")

    # TODO: pagination
    raise NotImplementedError()


@router.post(":upload", response_model=FileUploaded)
async def upload_single_file(
    file: UploadFile = File(...),
    storage_client: StorageApi = Depends(get_api_client(StorageApi)),
):
    # TODO: every file uploaded is sent to S3 and a link is returned
    # TODO: every session has a folder. A session is defined by the access token
    #

    # TODO: this is just a ping with retries
    ## await storage_client.get("/")

    return FileUploaded(
        filename=file.filename,
        content_type=file.content_type,
        hash=await eval_sha256_hash(file),
    )


@router.post(":upload-multiple", response_model=List[FileUploaded])
async def upload_multiple_files(files: List[UploadFile] = File(...)):
    # TODO: every file uploaded is sent to S3 and a link is returned
    # TODO: every session has a folder. A session is defined by the access token
    #
    async def go(file):
        return FileUploaded(
            filename=file.filename,
            content_type=file.content_type,
            hash=await eval_sha256_hash(file),
        )

    uploaded = await asyncio.gather(*[go(f) for f in files])
    return uploaded


_CONTENT = dedent(
    f"""
    <body>
    <form action="/{api_vtag}/files:upload" enctype="multipart/form-data" method="post">
    <input name="files" type="file" multiple>
    <input type="submit">
    </form>
    </body>
    """
)


@router.get("/upload-multiple-view")
async def files_upload_multiple_view():
    """Web form to upload files at http://localhost:8000/v0/files/upload-form-view

    Overcomes limitation of Swagger UI view
    NOTE: As of 2020-10-07, Swagger UI doesn't support multiple file uploads in the same form field
    """
    return HTMLResponse(content=_CONTENT)


async def eval_sha256_hash(file: UploadFile):
    # TODO: adaptive chunks depending on file size
    # SEE: https://stackoverflow.com/questions/17731660/hashlib-optimal-size-of-chunks-to-be-used-in-md5-update

    sha256_hash = hashlib.sha256()
    CHUNK_BYTES = 4 * 1024  # 4K blocks

    while True:
        chunk = await file.read(CHUNK_BYTES)
        if not chunk:
            break
        sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


@router.get("/{file_id}:download")
async def download_file(file_id: UUID):
    file_path: Path = current_file  # FIXME: tmp returns current file
    return FileResponse(
        file_path,
        media_type="application/octet-stream",
        filename=file_path.name,
        stat_result=file_path.stat(),
    )
