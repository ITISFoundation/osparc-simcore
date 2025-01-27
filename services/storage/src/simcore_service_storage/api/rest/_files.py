import asyncio
import logging
import urllib.parse
from typing import Annotated, cast

from aiohttp import web
from fastapi import APIRouter, Depends, Header, Request
from models_library.api_schemas_storage import (
    FileMetaDataGet,
    FileUploadCompleteFutureResponse,
    FileUploadCompleteLinks,
    FileUploadCompleteResponse,
    FileUploadCompleteState,
    FileUploadCompletionBody,
    FileUploadLinks,
    FileUploadSchema,
    SoftCopyBody,
)
from models_library.generics import Envelope
from models_library.projects_nodes_io import StorageFileID
from models_library.utils.fastapi_encoders import jsonable_encoder
from pydantic import AnyUrl, ByteSize, TypeAdapter
from servicelib.aiohttp import status

from ...constants import UPLOAD_TASKS_KEY
from ...dsm import get_dsm_provider
from ...exceptions.errors import FileMetaDataNotFoundError
from ...models import (
    FileDownloadQueryParams,
    FileDownloadResponse,
    FileMetaData,
    FileMetadataListQueryParams,
    FileUploadQueryParams,
    FileUploadResponseV1,
    LocationID,
    StorageQueryParamsBase,
    UploadLinks,
)
from ...simcore_s3_dsm import SimcoreS3DataManager
from ...utils.utils import create_upload_completion_task_name

_logger = logging.getLogger(__name__)

router = APIRouter(
    tags=[
        "files",
    ],
)


@router.get(
    "/locations/{location_id}/files/metadata",
    response_model=Envelope[list[FileMetaDataGet]],
)
async def list_files_metadata(
    query_params: Annotated[FileMetadataListQueryParams, Depends()],
    location_id: LocationID,
    request: Request,
):
    dsm = get_dsm_provider(request.app).get(location_id)
    data: list[FileMetaData] = await dsm.list_files(
        user_id=query_params.user_id,
        expand_dirs=query_params.expand_dirs,
        uuid_filter=query_params.uuid_filter
        or f"{query_params.project_id or ''}",  # NOTE: https://github.com/ITISFoundation/osparc-issues/issues/1593
        project_id=query_params.project_id,
    )
    return Envelope[list[FileMetaDataGet]](
        data=[FileMetaDataGet(**d.model_dump()) for d in data]
    )


@router.get(
    "/locations/{location_id}/files/{file_id}/metadata",
    response_model=Envelope[FileMetaDataGet],
)
async def get_file_metadata(
    query_params: Annotated[StorageQueryParamsBase, Depends()],
    location_id: LocationID,
    file_id: StorageFileID,
    request: Request,
    user_agent: Header(None),
):
    file_id = urllib.parse.unquote(f"{file_id}")

    dsm = get_dsm_provider(request.app).get(location_id)
    try:
        data = await dsm.get_file(
            user_id=query_params.user_id,
            file_id=file_id,
        )
    except FileMetaDataNotFoundError:
        # NOTE: LEGACY compatibility
        # This is what happens Larry... data must be an empty {} or else some old dynamic services will FAIL (sic)
        # Cannot remove until we retire all legacy services
        # https://github.com/ITISFoundation/osparc-simcore/issues/5676
        # https://github.com/ITISFoundation/osparc-simcore/blob/cfdf4f86d844ebb362f4f39e9c6571d561b72897/services/storage/client-sdk/python/simcore_service_storage_sdk/models/file_meta_data_enveloped.py#L34
        return Envelope[FileMetaDataGet](
            data=None,
            error="No result found",  # NOTE: LEGACY compatibility
        )

    if user_agent == "OpenAPI-Generator/0.1.0/python":
        # NOTE: LEGACY compatiblity with API v0.1.0
        # SEE models used in sdk in:
        # https://github.com/ITISFoundation/osparc-simcore/blob/cfdf4f86d844ebb362f4f39e9c6571d561b72897/services/storage/client-sdk/python/simcore_service_storage_sdk/models/file_meta_data_enveloped.py#L34
        # https://github.com/ITISFoundation/osparc-simcore/blob/cfdf4f86d844ebb362f4f39e9c6571d561b72897/services/storage/client-sdk/python/simcore_service_storage_sdk/models/file_meta_data_type.py#L34
        return Envelope[FileMetaDataGet](
            data=FileMetaDataGet(
                file_uuid=data.file_uuid,
                location_id=data.location_id,
                location=data.location,
                bucket_name=data.bucket_name,
                object_name=data.object_name,
                project_id=data.project_id,
                project_name=data.project_name,
                node_id=data.node_id,
                node_name=data.node_name,
                file_name=data.file_name,
                user_id=data.user_id,
                user_name=None,
            )
        )

    return Envelope[FileMetaDataGet](data=FileMetaDataGet(**data.model_dump()))


@router.get(
    "/locations/{location_id}/files/{file_id}",
    response_model=Envelope[FileDownloadResponse],
)
async def download_file(
    query_params: FileDownloadQueryParams,
    location_id: LocationID,
    file_id: StorageFileID,
    request: Request,
) -> Envelope[FileDownloadResponse]:
    file_id = urllib.parse.unquote(f"{file_id}")
    dsm = get_dsm_provider(request.app).get(location_id)
    link = await dsm.create_file_download_link(
        query_params.user_id, file_id, query_params.link_type
    )
    return Envelope[FileDownloadResponse](data=FileDownloadResponse(link=link))


@router.put(
    "/locations/{location_id}/files/{file_id}",
    response_model=Envelope[FileUploadResponseV1] | Envelope[FileUploadSchema],
)
async def upload_file(
    query_params: FileUploadQueryParams,
    location_id: LocationID,
    file_id: StorageFileID,
    request: Request,
):
    file_id = urllib.parse.unquote(f"{file_id}")
    """creates upload file links:

    This function covers v1 and v2 versions of the handler.
    Note: calling this entrypoint on an already existing file will overwrite that file. That file will be deleted
    before the upload takes place.

    v1 rationale:
        - client calls this handler, which returns a single link (either direct S3 or presigned) to the S3 backend
        - client uploads the file
        - storage relies on lazy update to find if the file is finished uploaded (when client calls get_file_meta_data, or if the dsm_cleaner goes over it after the upload time is expired)

    v2 rationale:
        - client calls this handler, which returns a FileUploadSchema object containing 1 or more links (either S3/presigned links)
        - client uploads the file (by chunking it if there are more than 1 presigned link)
        - client calls complete_upload handle which will reconstruct the file on S3 backend
        - client waits for completion to finish and then the file is accessible on S3 backend


    Use-case v1: query.file_size is not defined, returns a PresignedLink model (backward compatibility)
    Use-case v1.1: if query.link_type=presigned or None, returns a presigned link (limited to a single 5GB file)
    Use-case v1.2: if query.link_type=s3, returns a s3 direct link (limited to a single 5TB file)

    User-case v2: query.is_directory is True (query.file_size is forced to -1), returns an s3 path where to upload all the content of the directory
    User-case v2: if query.file_size is defined, returns a FileUploadSchema model, expects client to call "complete_upload" when the file is finished uploading
    Use-case v2.1: if query.file_size == 0 and query.link_type=presigned or None, returns a single presigned link inside FileUploadSchema (limited to a single 5Gb file)
    Use-case v2.2: if query.file_size > 0 and query.link_type=presigned or None, returns 1 or more presigned links depending on the file size (limited to a single 5TB file)
    Use-case v2.3: if query.link_type=s3 and query.file_size>=0, returns a single s3 direct link (limited to a single 5TB file)
    """

    dsm = get_dsm_provider(request.app).get(location_id)
    links: UploadLinks = await dsm.create_file_upload_links(
        user_id=query_params.user_id,
        file_id=file_id,
        link_type=query_params.link_type,
        file_size_bytes=query_params.file_size or ByteSize(0),
        is_directory=query_params.is_directory,
        sha256_checksum=query_params.sha256_checksum,
    )
    if query_params.is_v1_upload:
        # return v1 response
        assert len(links.urls) == 1  # nosec
        return Envelope[FileUploadResponseV1](
            data=FileUploadResponseV1(link=links.urls[0])
        )

    # v2 response
    abort_url = request.url.join(
        request.app.router["abort_upload_file"]
        .url_for(
            location_id=f"{location_id}",
            file_id=urllib.parse.quote(file_id, safe=""),
        )
        .with_query(user_id=query_params.user_id)
    )
    complete_url = request.url.join(
        request.app.router["complete_upload_file"]
        .url_for(
            location_id=f"{location_id}",
            file_id=urllib.parse.quote(file_id, safe=""),
        )
        .with_query(user_id=query_params.user_id)
    )
    v2_response = FileUploadSchema(
        chunk_size=links.chunk_size,
        urls=links.urls,
        links=FileUploadLinks(
            abort_upload=TypeAdapter(AnyUrl).validate_python(f"{abort_url}"),
            complete_upload=TypeAdapter(AnyUrl).validate_python(f"{complete_url}"),
        ),
    )
    return Envelope[FileUploadSchema](data=v2_response)


@router.post(
    "/locations/{location_id}/files/{file_id}:abort",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def abort_upload_file(
    query_params: Annotated[StorageQueryParamsBase, Depends()],
    location_id: LocationID,
    file_id: StorageFileID,
    request: Request,
):
    dsm = get_dsm_provider(request.app).get(location_id)
    await dsm.abort_file_upload(query_params.user_id, file_id)


@router.post(
    "/locations/{location_id}/files/{file_id}:complete",
    response_model=Envelope[FileUploadCompleteResponse],
)
async def complete_upload_file(
    query_params: Annotated[StorageQueryParamsBase, Depends()],
    location_id: LocationID,
    file_id: StorageFileID,
    body: Annotated[FileUploadCompletionBody, Depends()],
    request: Request,
):
    dsm = get_dsm_provider(request.app).get(location_id)
    # NOTE: completing a multipart upload on AWS can take up to several minutes
    # therefore we wait a bit to see if it completes fast and return a 204
    # if it returns slow we return a 202 - Accepted, the client will have to check later
    # for completeness
    task = asyncio.create_task(
        dsm.complete_file_upload(file_id, query_params.user_id, body.parts),
        name=create_upload_completion_task_name(query_params.user_id, file_id),
    )
    request.app[UPLOAD_TASKS_KEY][task.get_name()] = task
    assert request.transport  # nosec
    ip_addr, port = request.transport.get_extra_info(
        "sockname"
    )  # https://docs.python.org/3/library/asyncio-protocol.html#asyncio.BaseTransport.get_extra_info
    route = (
        request.app.router["is_completed_upload_file"]
        .url_for(
            location_id=f"{location_id}",
            file_id=urllib.parse.quote(file_id, safe=""),
            future_id=task.get_name(),
        )
        .with_query(user_id=query_params.user_id)
    )
    complete_task_state_url = f"{request.url.scheme}://{ip_addr}:{port}{route}"
    response = FileUploadCompleteResponse(
        links=FileUploadCompleteLinks(
            state=TypeAdapter(AnyUrl).validate_python(complete_task_state_url)
        )
    )
    return Envelope[FileUploadCompleteResponse](data=response)


@router.post(
    "/locations/{location_id}/files/{file_id}:complete/futures/{future_id}",
    response_model=FileUploadCompleteFutureResponse,
)
async def is_completed_upload_file(
    query_params: Annotated[StorageQueryParamsBase, Depends()],
    location_id: LocationID,
    file_id: StorageFileID,
    future_id: str,
    request: Request,
):
    # NOTE: completing a multipart upload on AWS can take up to several minutes
    # therefore we wait a bit to see if it completes fast and return a 204
    # if it returns slow we return a 202 - Accepted, the client will have to check later
    # for completeness
    task_name = create_upload_completion_task_name(query_params.user_id, file_id)
    assert task_name == future_id  # nosec
    # first check if the task is in the app
    if task := request.app[UPLOAD_TASKS_KEY].get(task_name):
        if task.done():
            new_fmd: FileMetaData = task.result()
            request.app[UPLOAD_TASKS_KEY].pop(task_name)
            response = FileUploadCompleteFutureResponse(
                state=FileUploadCompleteState.OK, e_tag=new_fmd.entity_tag
            )
        else:
            # the task is still running
            response = FileUploadCompleteFutureResponse(
                state=FileUploadCompleteState.NOK
            )
        return jsonable_encoder(response, by_alias=True)  # type: ignore[no-any-return] # middleware takes care of enveloping
    # there is no task, either wrong call or storage was restarted
    # we try to get the file to see if it exists in S3
    dsm = get_dsm_provider(request.app).get(location_id)
    if fmd := await dsm.get_file(
        user_id=query_params.user_id,
        file_id=file_id,
    ):
        response = FileUploadCompleteFutureResponse(
            state=FileUploadCompleteState.OK, e_tag=fmd.entity_tag
        )
        return jsonable_encoder(response, by_alias=True)  # type: ignore[no-any-return] # middleware takes care of enveloping
    raise web.HTTPNotFound(
        reason="Not found. Upload could not be completed. Please try again and contact support if it fails again."
    )


@router.delete(
    "/locations/{location_id}/files/{file_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_file(
    query_params: Annotated[StorageQueryParamsBase, Depends()],
    location_id: LocationID,
    file_id: StorageFileID,
    request: Request,
):
    dsm = get_dsm_provider(request.app).get(location_id)
    await dsm.delete_file(query_params.user_id, file_id)


@router.post("/files/{file_id}:soft-copy", response_model=FileMetaDataGet)
async def copy_as_soft_link(
    query_params: Annotated[StorageQueryParamsBase, Depends()],
    file_id: StorageFileID,
    body: Annotated[SoftCopyBody, Depends()],
    request: Request,
):
    dsm = cast(
        SimcoreS3DataManager,
        get_dsm_provider(request.app).get(SimcoreS3DataManager.get_location_id()),
    )
    file_link = await dsm.create_soft_link(query_params.user_id, file_id, body.link_id)

    return FileMetaDataGet(**file_link.model_dump())
