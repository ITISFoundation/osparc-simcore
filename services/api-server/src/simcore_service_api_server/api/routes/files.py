import asyncio
import json
import logging
import re
from collections import deque
from datetime import datetime
from mimetypes import guess_type
from textwrap import dedent
from typing import Dict, List, Optional
from urllib.parse import quote
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, File, Header, UploadFile, status
from fastapi.exceptions import HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import ValidationError

from ..._meta import api_vtag
from ...models.schemas.files import FileMetadata
from ...modules.storage import StorageApi, StorageFileMetaData
from ..dependencies.authentication import get_current_user_id
from ..dependencies.services import get_api_client
from .files_faker import the_fake_impl

logger = logging.getLogger(__name__)
router = APIRouter()


## FILES ---------------------------------------------------------------------------------
#
# - WARNING: the order of the router-decorated functions MATTER
# - TODO: pagination ?
# - TODO: extend :search as https://cloud.google.com/apis/design/custom_methods ?
#
#
FILE_ID_PATTERN = re.compile(r"^api\/(?P<file_id>[\w-]+)\/(?P<filename>.+)$")


def convert_metadata(stored_file_meta: StorageFileMetaData) -> FileMetadata:
    # extracts fields from api/{file_id}/{filename}
    match = FILE_ID_PATTERN.match(stored_file_meta.file_id or "")
    if not match:
        raise ValueError(f"Invalid file_id {stored_file_meta.file_id} in file metadata")

    file_id, filename = match.groups()

    meta = FileMetadata(
        file_id=file_id,
        filename=filename,
        content_type=guess_type(filename)[0],
        checksum=stored_file_meta.entity_tag,
    )
    return meta


@router.get("", response_model=List[FileMetadata])
async def list_files(
    storage_client: StorageApi = Depends(get_api_client(StorageApi)),
    user_id: int = Depends(get_current_user_id),
):
    """ Gets metadata for all file resources """

    stored_files: List[StorageFileMetaData] = await storage_client.list_files(user_id)

    # Adapts storage API model to API model
    files_metadata = deque()
    for stored_file_meta in stored_files:
        try:
            assert stored_file_meta.user_id == user_id  # nosec
            assert stored_file_meta.file_id  # nosec

            meta = convert_metadata(stored_file_meta)

        except (ValidationError, ValueError, AttributeError) as err:
            logger.warning(
                "Skipping corrupted entry in storage '%s' (%s)"
                "TIP: check this entry in file_meta_data table.",
                stored_file_meta.file_uuid,
                err,
            )

        else:
            files_metadata.append(meta)

    return list(files_metadata)


@router.post(":upload", response_model=FileMetadata)
async def upload_file(
    file: UploadFile = File(...),
    content_length: Optional[str] = Header(None),
    storage_client: StorageApi = Depends(get_api_client(StorageApi)),
    user_id: int = Depends(get_current_user_id),
):
    """Uploads a single file to the system    """
    # TODO: For the moment we upload file here and re-upload to S3
    # using a pre-signed link. This is far from ideal since we are using the api-server as a
    # passby service for all uploaded data which can be a lot.
    # Next refactor should consider a solution that directly uploads from the client to S3
    # avoiding the data trafic via this service
    #

    # assign file_id.
    meta: FileMetadata = await FileMetadata.create_from_uploaded(
        file, file_size=content_length, created_at=datetime.utcnow().isoformat()
    )
    logger.debug("Assigned id: %s of %s bytes", meta, content_length)

    # upload to S3 using pre-signed link
    presigned_upload_link = await storage_client.get_upload_link(
        user_id, meta.file_id, meta.filename
    )

    logger.info("Uploading %s to %s ...", meta, presigned_upload_link)

    async with httpx.AsyncClient(timeout=httpx.Timeout(5.0, write=3600)) as client:
        assert meta.content_type  # nosec

        # pylint: disable=protected-access
        # NOTE: _file attribute is a file-like object of ile.file which is
        # a https://docs.python.org/3/library/tempfile.html#tempfile.TemporaryFile
        #
        resp = await client.put(
            presigned_upload_link,
            files={"upload-file": (meta.filename, file.file._file, meta.content_type)},
        )
        resp.raise_for_status()

    # update checksum
    entity_tag = json.loads(resp.headers.get("Etag"))
    meta.checksum = entity_tag
    return meta


# DISABLED @router.post(":upload-multiple", response_model=List[FileMetadata])
async def upload_files(files: List[UploadFile] = File(...)):
    """ Uploads multiple files to the system """
    # MaG suggested a single function that can upload one or multiple files instead of having
    # two of them. Tried something like upload_file( files: Union[List[UploadFile], File] ) but it
    # produces an error in the generated openapi.json
    #
    # Since there is no inmediate need of this functions, we decided to disable it
    #
    async def save_file(file):
        metadata = await the_fake_impl.save(file)
        return metadata

    uploaded = await asyncio.gather(*[save_file(f) for f in files])
    return uploaded


@router.get("/{file_id}", response_model=FileMetadata)
async def get_file(
    file_id: UUID,
    storage_client: StorageApi = Depends(get_api_client(StorageApi)),
    user_id: int = Depends(get_current_user_id),
):
    """ Gets metadata for a given file resource """

    try:
        stored_files: List[StorageFileMetaData] = await storage_client.search_files(
            user_id, file_id
        )
        if not stored_files:
            raise ValueError("Not found in storage")

        stored_file_meta = stored_files[0]
        assert stored_file_meta.user_id == user_id  # nosec
        assert stored_file_meta.file_id  # nosec

        # Adapts storage API model to API model
        meta = convert_metadata(stored_file_meta)
        return meta

    except (ValueError, ValidationError) as err:
        logger.debug("File %d not found: %s", file_id, err)
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=f"File with identifier {file_id} not found",
        ) from err


@router.post("/{file_id}:download")
async def download_file(
    file_id: UUID,
    storage_client: StorageApi = Depends(get_api_client(StorageApi)),
    user_id: int = Depends(get_current_user_id),
):
    # gets meta
    meta: FileMetadata = await get_file(file_id, storage_client, user_id)

    # download from S3 using pre-signed link
    presigned_download_link = await storage_client.get_download_link(
        user_id, meta.file_id, meta.filename
    )
    logger.info("Downloading %s to %s ...", meta, presigned_download_link)

    async def _download_stream():
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0, read=3600)) as client:
            async with client.stream("GET", presigned_download_link) as resp:
                async for chunk in resp.aiter_bytes():
                    yield chunk

                resp.raise_for_status()

    # attach download stream to the streamed response
    def _build_headers() -> Dict:
        # Adapted from from starlatte/responses.py::FileResponse.__init__
        content_disposition_filename = quote(meta.filename)
        if content_disposition_filename != meta.filename:
            content_disposition = "attachment; filename*=utf-8''{}".format(
                content_disposition_filename
            )
        else:
            content_disposition = 'attachment; filename="{}"'.format(meta.filename)
        return {"content-disposition": content_disposition}

    # FIXME: this DOES NOT WORK, it only downloads one chunk
    return StreamingResponse(
        _download_stream(), media_type=meta.content_type, headers=_build_headers()
    )


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
