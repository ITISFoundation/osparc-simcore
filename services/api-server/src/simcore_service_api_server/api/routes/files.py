import asyncio
import logging
import re
from collections import deque
from mimetypes import guess_type
from textwrap import dedent
from typing import Dict, List
from urllib.parse import quote
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, File, UploadFile, status
from fastapi.exceptions import HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import ValidationError
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_delay,
    wait_fixed,
)

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

            # extracts fields from api/{file_id}/{filename}
            match = FILE_ID_PATTERN.match(stored_file_meta.file_id)
            assert match  # nosec
            file_id, filename = match.group()

            meta = FileMetadata(
                file_id=file_id,
                filename=filename,
                content_type=guess_type(filename),
                checksum=stored_file_meta.entity_tag,
            )

        except (ValidationError, ValueError, AttributeError) as err:
            logger.warning(
                "Skipping corrupted entry in storage: %s (%s).", stored_file_meta, err
            )

        else:
            files_metadata.append(meta)

    return list(files_metadata)


@router.post(":upload", response_model=FileMetadata)
async def upload_file(
    file: UploadFile = File(...),
    storage_client: StorageApi = Depends(get_api_client(StorageApi)),
    user_id: int = Depends(get_current_user_id),
):
    """Uploads a single file to the system    """
    # TODO: for the moment we upload file here and re-upload to S3
    # using a pre-signed link. This is far from ideal since we are using the api-server as a
    # passby service for all uploaded data which can be a lot.
    # Next refactor should consider a solution that directly uploads from the client to S3
    # avoiding the data trafic via this service
    #

    # assign file_id
    # FIXME: create file-id with time-stamp instead so we can stream up
    # as chunks are arriving?
    # can perhaps digest content on the fly
    #
    meta: FileMetadata = await FileMetadata.create_from_uploaded(file)
    assert meta.content_type  # nosec

    await file.seek(0)  # reset since previous call read file to create checksum

    # upload to S3 using pre-signed link
    presigned_upload_link = await storage_client.get_upload_link(
        user_id, meta.file_id, meta.filename
    )
    async with httpx.AsyncClient() as client:
        resp = await client.put(
            presigned_upload_link,
            files={"upload-file": (meta.filename, file, meta.content_type)},
        )
        resp.raise_for_status()
        ## e_tag = json.loads(resp.headers.get("Etag", None))
        # FIXME: get ETag from resp as SAN does saves re-calling storage

    # FIXME: forgot error handling

    # validate upload and update checksum by getting storage metadata
    #
    # NOTE: storage service is observing S3 to verify upload, which means that we need to give
    #  a few seconds before the file_metadata table is updated
    #
    async for attempt in AsyncRetrying(
        retry=retry_if_exception_type(ValueError),
        wait=wait_fixed(2),
        stop=stop_after_delay(10),
    ):
        with attempt:
            stored_files: List[StorageFileMetaData] = await storage_client.search_files(
                user_id, meta.file_id
            )
            if not stored_files:
                raise ValueError("Not found in storage")
            stored_file_meta = stored_files[0]
            assert stored_file_meta.user_id == user_id  # nosec
            assert stored_file_meta.file_id  # nosec

            # the initial checksum was used to generate the file_id but
            # for consistency we will be using the one provided by storage
            meta.checksum = stored_file_meta.etag
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
        try:
            # extracts fields from api/{file_id}/{filename}
            match = FILE_ID_PATTERN.match(stored_file_meta.file_id)
            assert match  # nosec

            _file_id, _filename = match.group()
            assert str(file_id) == _file_id  # nosec

            meta = FileMetadata(
                file_id=file_id,
                filename=_filename,
                content_type=guess_type(_filename),
                checksum=stored_file_meta.entity_tag,
            )

        except (ValidationError, AttributeError) as err:
            logger.warning(
                "Skipping corrupted entry in storage: %s (%s).", stored_file_meta, err
            )
            raise ValueError("Corrupted entry in storage") from err
        else:
            return meta

    except ValueError as err:
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

    async def _download_stream():
        async with httpx.AsyncClient() as client:
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
