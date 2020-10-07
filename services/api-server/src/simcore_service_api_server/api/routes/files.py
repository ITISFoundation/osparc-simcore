import asyncio
import hashlib
from textwrap import dedent
from typing import List

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import HTMLResponse

from ...__version__ import api_vtag
from ...models.schemas.files import FileUploaded

router = APIRouter()


@router.get("")
async def list_files():
    """ Lists all user's files """
    # TODO: pagination
    pass


@router.post(":upload", response_model=FileUploaded)
async def upload_single_file(file: UploadFile = File(...)):
    # TODO: every file uploaded is sent to S3 and a link is returned
    # TODO: every session has a folder. A session is defined by the access token
    #
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
