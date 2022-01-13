import asyncio
import json
import logging
from collections import deque
from datetime import datetime
from textwrap import dedent
from typing import List, Optional
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends
from fastapi import File as FileParam
from fastapi import Header, UploadFile, status
from fastapi.exceptions import HTTPException
from fastapi.responses import HTMLResponse
from pydantic import ValidationError
from starlette.responses import RedirectResponse

from ..._meta import API_VTAG
from ...models.schemas.files import File
from ...modules.storage import StorageApi, StorageFileMetaData, to_file_api_model
from ..dependencies.authentication import get_current_user_id
from ..dependencies.services import get_api_client

logger = logging.getLogger(__name__)
router = APIRouter()


## FILES ---------------------------------------------------------------------------------
#
# - WARNING: the order of the router-decorated functions MATTER
# - TODO: pagination ?
# - TODO: extend :search as https://cloud.google.com/apis/design/custom_methods ?
#
#

common_error_responses = {
    status.HTTP_404_NOT_FOUND: {"description": "File not found"},
}


@router.get("", response_model=List[File])
async def list_files(
    storage_client: StorageApi = Depends(get_api_client(StorageApi)),
    user_id: int = Depends(get_current_user_id),
):
    """Lists all files stored in the system"""

    stored_files: List[StorageFileMetaData] = await storage_client.list_files(user_id)

    # Adapts storage API model to API model
    files_meta = deque()
    for stored_file_meta in stored_files:
        try:
            assert stored_file_meta.user_id == user_id  # nosec
            assert stored_file_meta.file_id  # nosec

            file_meta: File = to_file_api_model(stored_file_meta)

        except (ValidationError, ValueError, AttributeError) as err:
            logger.warning(
                "Skipping corrupted entry in storage '%s' (%s)"
                "TIP: check this entry in file_meta_data table.",
                stored_file_meta.file_uuid,
                err,
            )

        else:
            files_meta.append(file_meta)

    return list(files_meta)


@router.put("/content", response_model=File)
async def upload_file(
    file: UploadFile = FileParam(...),
    content_length: Optional[str] = Header(None),
    storage_client: StorageApi = Depends(get_api_client(StorageApi)),
    user_id: int = Depends(get_current_user_id),
):
    """Uploads a single file to the system"""
    # TODO: For the moment we upload file here and re-upload to S3
    # using a pre-signed link. This is far from ideal since we are using the api-server as a
    # passby service for all uploaded data which can be a lot.
    # Next refactor should consider a solution that directly uploads from the client to S3
    # avoiding the data trafic via this service

    # assign file_id.
    file_meta: File = await File.create_from_uploaded(
        file, file_size=content_length, created_at=datetime.utcnow().isoformat()
    )
    logger.debug("Assigned id: %s of %s bytes", file_meta, content_length)

    # upload to S3 using pre-signed link
    presigned_upload_link = await storage_client.get_upload_link(
        user_id, file_meta.id, file_meta.filename
    )

    logger.info("Uploading %s to %s ...", file_meta, presigned_upload_link)
    try:
        #
        # FIXME: TN was uploading files ~1GB and would raise httpx.ReadTimeout.
        #  - Review timeout config (see api/dependencies/files.py)
        #
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(5.0, read=60.0, write=3600.0)
        ) as client:
            assert file_meta.content_type  # nosec

            resp = await client.put(presigned_upload_link, data=await file.read())
            resp.raise_for_status()

    except httpx.TimeoutException as err:
        # SEE https://httpstatuses.com/504
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"Uploading file reached maximum time limit. Details: {file_meta}",
        ) from err

    # update checksum
    entity_tag = json.loads(resp.headers.get("Etag"))
    file_meta.checksum = entity_tag
    return file_meta


# DISABLED @router.post(":upload-multiple", response_model=List[FileMetadata])
async def upload_files(files: List[UploadFile] = FileParam(...)):
    """Uploads multiple files to the system"""
    # MaG suggested a single function that can upload one or multiple files instead of having
    # two of them. Tried something like upload_file( files: Union[List[UploadFile], File] ) but it
    # produces an error in the generated openapi.json
    #
    # Since there is no inmediate need of this functions, we decided to disable it
    #
    async def save_file(file):
        from ._files_faker import the_fake_impl

        metadata = await the_fake_impl.save(file)
        return metadata

    uploaded = await asyncio.gather(*[save_file(f) for f in files])
    return uploaded


@router.get("/{file_id}", response_model=File, responses={**common_error_responses})
async def get_file(
    file_id: UUID,
    storage_client: StorageApi = Depends(get_api_client(StorageApi)),
    user_id: int = Depends(get_current_user_id),
):
    """Gets metadata for a given file resource"""

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
        file_meta = to_file_api_model(stored_file_meta)
        return file_meta

    except (ValueError, ValidationError) as err:
        logger.debug("File %d not found: %s", file_id, err)
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=f"File with identifier {file_id} not found",
        ) from err


@router.get(
    "/{file_id}/content",
    response_class=RedirectResponse,
    responses={
        **common_error_responses,
        200: {
            "content": {
                "application/octet-stream": {
                    "schema": {"type": "string", "format": "binary"}
                },
                "text/plain": {"schema": {"type": "string"}},
            },
            "description": "Returns a arbitrary binary data",
        },
    },
)
async def download_file(
    file_id: UUID,
    storage_client: StorageApi = Depends(get_api_client(StorageApi)),
    user_id: int = Depends(get_current_user_id),
):
    # NOTE: application/octet-stream is defined as "arbitrary binary data" in RFC 2046,
    # gets meta
    file_meta: File = await get_file(file_id, storage_client, user_id)

    # download from S3 using pre-signed link
    presigned_download_link = await storage_client.get_download_link(
        user_id, file_meta.id, file_meta.filename
    )

    logger.info("Downloading %s to %s ...", file_meta, presigned_download_link)
    return RedirectResponse(presigned_download_link)


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
        <form action="/{API_VTAG}/files:upload" enctype="multipart/form-data" method="post">
        <input name="files" type="file" multiple>
        <input type="submit">
        </form>
        </body>
        """
        )
    )
