import asyncio
import datetime
import io
import logging
from textwrap import dedent
from typing import IO, Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi import File as FileParam
from fastapi import Header, Request, UploadFile, status
from fastapi.exceptions import HTTPException
from fastapi.responses import HTMLResponse
from models_library.projects_nodes_io import StorageFileID
from pydantic import ValidationError, parse_obj_as
from servicelib.fastapi.requests_decorators import cancel_on_disconnect
from simcore_sdk.node_ports_common.constants import SIMCORE_LOCATION
from simcore_sdk.node_ports_common.filemanager import (
    UploadableFileObject,
    UploadedFile,
    UploadedFolder,
)
from simcore_sdk.node_ports_common.filemanager import upload_path as storage_upload_path
from starlette.responses import RedirectResponse

from ..._meta import API_VTAG
from ...models.pagination import Page, PaginationParams
from ...models.schemas.errors import ErrorGet
from ...models.schemas.files import File
from ...services.storage import StorageApi, StorageFileMetaData, to_file_api_model
from ..dependencies.authentication import get_current_user_id
from ..dependencies.services import get_api_client
from ._common import API_SERVER_DEV_FEATURES_ENABLED

_logger = logging.getLogger(__name__)
router = APIRouter()

## FILES ---------------------------------------------------------------------------------
#
# - WARNING: the order of the router-decorated functions MATTER
# - TODO: extend :search as https://cloud.google.com/apis/design/custom_methods ?
#
#

_common_error_responses = {
    status.HTTP_404_NOT_FOUND: {
        "description": "File not found",
        "model": ErrorGet,
    },
}


@router.get("", response_model=list[File])
async def list_files(
    storage_client: Annotated[StorageApi, Depends(get_api_client(StorageApi))],
    user_id: Annotated[int, Depends(get_current_user_id)],
):
    """Lists all files stored in the system

    SEE get_files_page for a paginated version of this function
    """

    stored_files: list[StorageFileMetaData] = await storage_client.list_files(user_id)

    # Adapts storage API model to API model
    all_files: list[File] = []
    for stored_file_meta in stored_files:
        try:
            assert stored_file_meta.file_id  # nosec

            file_meta: File = to_file_api_model(stored_file_meta)

        except (ValidationError, ValueError, AttributeError) as err:
            _logger.warning(
                "Skipping corrupted entry in storage '%s' (%s)"
                "TIP: check this entry in file_meta_data table.",
                stored_file_meta.file_uuid,
                err,
            )

        else:
            all_files.append(file_meta)

    return all_files


@router.get(
    "/page",
    response_model=Page[File],
    include_in_schema=API_SERVER_DEV_FEATURES_ENABLED,
)
async def get_files_page(
    storage_client: Annotated[StorageApi, Depends(get_api_client(StorageApi))],
    user_id: Annotated[int, Depends(get_current_user_id)],
    page_params: Annotated[PaginationParams, Depends()],
):
    assert storage_client  # nosec
    assert user_id  # nosec

    msg = f"get_files_page of user_id={user_id!r} with page_params={page_params!r}. SEE https://github.com/ITISFoundation/osparc-issues/issues/952"
    raise NotImplementedError(msg)


def _get_spooled_file_size(file_io: IO) -> int:
    file_io.seek(0, io.SEEK_END)
    file_size = file_io.tell()
    file_io.seek(0)
    return file_size


@router.put("/content", response_model=File)
@cancel_on_disconnect
async def upload_file(
    request: Request,
    file: Annotated[UploadFile, FileParam(...)],
    user_id: Annotated[int, Depends(get_current_user_id)],
    content_length: str | None = Header(None),  # noqa: B008
):
    """Uploads a single file to the system"""
    # TODO: For the moment we upload file here and re-upload to S3
    # using a pre-signed link. This is far from ideal since we are using the api-server as a
    # passby service for all uploaded data which can be a lot.
    # Next refactor should consider a solution that directly uploads from the client to S3
    # avoiding the data trafic via this service

    assert request  # nosec

    file_size = await asyncio.get_event_loop().run_in_executor(
        None, _get_spooled_file_size, file.file
    )
    # assign file_id.
    file_meta: File = await File.create_from_uploaded(
        file,
        file_size=file_size,
        created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    )
    _logger.debug(
        "Assigned id: %s of %s bytes (content-length), real size %s bytes",
        file_meta,
        content_length,
        file_size,
    )

    # upload to S3 using pre-signed link
    upload_result: UploadedFolder | UploadedFile = await storage_upload_path(
        user_id=user_id,
        store_id=SIMCORE_LOCATION,
        store_name=None,
        s3_object=parse_obj_as(
            StorageFileID, f"api/{file_meta.id}/{file_meta.filename}"
        ),
        path_to_upload=UploadableFileObject(file.file, file.filename, file_size),
        io_log_redirect_cb=None,
    )
    assert isinstance(upload_result, UploadedFile)

    file_meta.checksum = upload_result.etag
    return file_meta


# MaG suggested a single function that can upload one or multiple files instead of having
# two of them. Tried something like upload_file( files: Union[list[UploadFile], File] ) but it
# produces an error in the generated openapi.json
#
# Since there is no inmediate need of this functions, we decided to disable it
# but keep it here as a reminder for future re-designs
#
async def upload_files(files: list[UploadFile] = FileParam(...)):
    """Uploads multiple files to the system"""
    raise NotImplementedError


@router.get("/{file_id}", response_model=File, responses={**_common_error_responses})
async def get_file(
    file_id: UUID,
    storage_client: Annotated[StorageApi, Depends(get_api_client(StorageApi))],
    user_id: Annotated[int, Depends(get_current_user_id)],
):
    """Gets metadata for a given file resource"""

    try:
        stored_files: list[StorageFileMetaData] = await storage_client.search_files(
            user_id, file_id
        )
        if not stored_files:
            msg = "Not found in storage"
            raise ValueError(msg)  # noqa: TRY301

        stored_file_meta = stored_files[0]
        assert stored_file_meta.file_id  # nosec

        # Adapts storage API model to API model
        return to_file_api_model(stored_file_meta)

    except (ValueError, ValidationError) as err:
        _logger.debug("File %d not found: %s", file_id, err)
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=f"File with identifier {file_id} not found",
        ) from err


@router.delete(
    "/{file_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={**_common_error_responses},
    include_in_schema=API_SERVER_DEV_FEATURES_ENABLED,
)
async def delete_file(
    file_id: UUID,
    storage_client: Annotated[StorageApi, Depends(get_api_client(StorageApi))],
    user_id: Annotated[int, Depends(get_current_user_id)],
):
    assert storage_client  # nsoec

    msg = f"delete file {file_id=} of {user_id=}. SEE https://github.com/ITISFoundation/osparc-issues/issues/952"
    raise NotImplementedError(msg)


@router.get(
    "/{file_id}/content",
    response_class=RedirectResponse,
    responses={
        **_common_error_responses,
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
    storage_client: Annotated[StorageApi, Depends(get_api_client(StorageApi))],
    user_id: Annotated[int, Depends(get_current_user_id)],
):
    # NOTE: application/octet-stream is defined as "arbitrary binary data" in RFC 2046,
    # gets meta
    file_meta: File = await get_file(file_id, storage_client, user_id)

    # download from S3 using pre-signed link
    presigned_download_link = await storage_client.get_download_link(
        user_id, file_meta.id, file_meta.filename
    )

    _logger.info("Downloading %s to %s ...", file_meta, presigned_download_link)
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
