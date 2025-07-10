import logging
from typing import Annotated, Final, cast
from urllib.parse import quote

from fastapi import APIRouter, Depends, Header, Request
from models_library.api_schemas_rpc_async_jobs.async_jobs import AsyncJobFilter
from models_library.api_schemas_storage.storage_schemas import (
    FileMetaDataGet,
    FileMetaDataGetv010,
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
from models_library.projects_nodes_io import LocationID, StorageFileID
from pydantic import AnyUrl, ByteSize, TypeAdapter
from servicelib.aiohttp import status
from servicelib.celery.models import TaskFilter, TaskUUID
from servicelib.celery.task_manager import TaskManager
from servicelib.logging_utils import log_context
from yarl import URL

from ...dsm import get_dsm_provider
from ...exceptions.errors import FileMetaDataNotFoundError
from ...models import (
    FileDownloadQueryParams,
    FileDownloadResponse,
    FileMetaData,
    FileMetadataListQueryParams,
    FileUploadQueryParams,
    FileUploadResponseV1,
    StorageQueryParamsBase,
    UploadLinks,
)
from ...simcore_s3_dsm import SimcoreS3DataManager
from .._worker_tasks._files import complete_upload_file as remote_complete_upload_file
from .dependencies.celery import get_task_manager

_ASYNC_JOB_CLIENT_NAME: Final[str] = "STORAGE"


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
    "/locations/{location_id}/files/{file_id:path}/metadata",
    response_model=Envelope[FileMetaDataGet]
    | Envelope[FileMetaDataGetv010]
    | Envelope[dict],
)
async def get_file_metadata(
    query_params: Annotated[StorageQueryParamsBase, Depends()],
    location_id: LocationID,
    file_id: StorageFileID,
    user_agent: Annotated[str | None, Header()],
    request: Request,
):
    # NOTE: Used by legacy dynamic services -> MUST BE BACKWARDS COMPATIBLE
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
        return Envelope[dict](
            data={},
            error="No result found",  # NOTE: LEGACY compatibility
        )

    if user_agent == "OpenAPI-Generator/0.1.0/python":
        # NOTE: LEGACY compatiblity with API v0.1.0
        # SEE models used in sdk in:
        # https://github.com/ITISFoundation/osparc-simcore/blob/cfdf4f86d844ebb362f4f39e9c6571d561b72897/services/storage/client-sdk/python/simcore_service_storage_sdk/models/file_meta_data_enveloped.py#L34
        # https://github.com/ITISFoundation/osparc-simcore/blob/cfdf4f86d844ebb362f4f39e9c6571d561b72897/services/storage/client-sdk/python/simcore_service_storage_sdk/models/file_meta_data_type.py#L34
        return Envelope[FileMetaDataGetv010](
            data=FileMetaDataGetv010(
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
    "/locations/{location_id}/files/{file_id:path}",
    response_model=Envelope[FileDownloadResponse],
)
async def download_file(
    location_id: LocationID,
    file_id: StorageFileID,
    query_params: Annotated[FileDownloadQueryParams, Depends()],
    request: Request,
) -> Envelope[FileDownloadResponse]:
    # NOTE: Used by legacy dynamic services -> MUST BE BACKWARDS COMPATIBLE
    dsm = get_dsm_provider(request.app).get(location_id)
    link = await dsm.create_file_download_link(
        query_params.user_id, file_id, query_params.link_type
    )
    return Envelope[FileDownloadResponse](data=FileDownloadResponse(link=link))


@router.put(
    "/locations/{location_id}/files/{file_id:path}",
    response_model=Envelope[FileUploadResponseV1] | Envelope[FileUploadSchema],
)
async def upload_file(
    location_id: LocationID,
    file_id: StorageFileID,
    query_params: Annotated[FileUploadQueryParams, Depends()],
    request: Request,
):
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
    # NOTE: Used by legacy dynamic services with single presigned link -> MUST BE BACKWARDS COMPATIBLE
    dsm = get_dsm_provider(request.app).get(location_id)
    with log_context(
        logger=_logger, level=logging.DEBUG, msg=f"Creating upload links for {file_id=}"
    ):
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

    abort_url = (
        URL(f"{request.url}")
        .with_path(
            quote(
                request.app.url_path_for(
                    "abort_upload_file",
                    location_id=f"{location_id}",
                    file_id=file_id,
                ),
                safe=":/",
            ),
            encoded=True,
        )
        .with_query(user_id=query_params.user_id)
    )

    complete_url = (
        URL(f"{request.url}")
        .with_path(
            quote(
                request.app.url_path_for(
                    "complete_upload_file",
                    location_id=f"{location_id}",
                    file_id=file_id,
                ),
                safe=":/",
            ),
            encoded=True,
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
    "/locations/{location_id}/files/{file_id:path}:abort",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def abort_upload_file(
    location_id: LocationID,
    file_id: StorageFileID,
    query_params: Annotated[StorageQueryParamsBase, Depends()],
    request: Request,
):
    dsm = get_dsm_provider(request.app).get(location_id)
    await dsm.abort_file_upload(query_params.user_id, file_id)


_UNDEFINED_PRODUCT_NAME_FOR_WORKER_TASKS: Final[str] = (
    "undefinedproduct"  # NOTE: this is used to keep backwards compatibility with user of these APIs
)


@router.post(
    "/locations/{location_id}/files/{file_id:path}:complete",
    response_model=Envelope[FileUploadCompleteResponse],
    status_code=status.HTTP_202_ACCEPTED,
)
async def complete_upload_file(
    task_manager: Annotated[TaskManager, Depends(get_task_manager)],
    query_params: Annotated[StorageQueryParamsBase, Depends()],
    location_id: LocationID,
    file_id: StorageFileID,
    body: FileUploadCompletionBody,
    request: Request,
):
    # NOTE: completing a multipart upload on AWS can take up to several minutes
    # if it returns slow we return a 202 - Accepted, the client will have to check later
    # for completeness
    job_filter = AsyncJobFilter(
        user_id=query_params.user_id,
        product_name=_UNDEFINED_PRODUCT_NAME_FOR_WORKER_TASKS,  # NOTE: I would need to change the API here
        client_name=_ASYNC_JOB_CLIENT_NAME,
    )
    task_filter = TaskFilter.model_validate(job_filter.model_dump())
    task_uuid = await task_manager.send_task(
        task_name=remote_complete_upload_file.__name__,
        task_filter=task_filter,
        user_id=job_filter.user_id,
        location_id=location_id,
        file_id=file_id,
        body=body,
    )

    route = (
        URL(f"{request.url}")
        .with_path(
            quote(
                request.app.url_path_for(
                    "is_completed_upload_file",
                    location_id=f"{location_id}",
                    file_id=file_id,
                    future_id=f"{task_uuid}",
                ),
                safe=":/",
            ),
            encoded=True,
        )
        .with_query(user_id=query_params.user_id)
    )
    complete_task_state_url = f"{route}"

    response = FileUploadCompleteResponse(
        links=FileUploadCompleteLinks(
            state=TypeAdapter(AnyUrl).validate_python(complete_task_state_url)
        )
    )
    return Envelope[FileUploadCompleteResponse](data=response)


@router.post(
    "/locations/{location_id}/files/{file_id:path}:complete/futures/{future_id}",
    response_model=Envelope[FileUploadCompleteFutureResponse],
)
async def is_completed_upload_file(
    task_manager: Annotated[TaskManager, Depends(get_task_manager)],
    query_params: Annotated[StorageQueryParamsBase, Depends()],
    location_id: LocationID,
    file_id: StorageFileID,
    future_id: str,
):
    # NOTE: completing a multipart upload on AWS can take up to several minutes
    # therefore we wait a bit to see if it completes fast and return a 204
    # if it returns slow we return a 202 - Accepted, the client will have to check later
    # for completeness
    job_filter = AsyncJobFilter(
        user_id=query_params.user_id,
        product_name=_UNDEFINED_PRODUCT_NAME_FOR_WORKER_TASKS,  # NOTE: I would need to change the API here
        client_name=_ASYNC_JOB_CLIENT_NAME,
    )
    task_filter = TaskFilter.model_validate(job_filter.model_dump())
    task_status = await task_manager.get_task_status(
        task_filter=task_filter,
        task_uuid=TaskUUID(future_id),
    )
    # first check if the task is in the app
    if task_status.is_done:
        task_result = TypeAdapter(FileMetaData).validate_python(
            await task_manager.get_task_result(
                task_filter=task_filter,
                task_uuid=TaskUUID(future_id),
            )
        )
        new_fmd = task_result
        assert new_fmd.location_id == location_id  # nosec
        assert new_fmd.file_id == file_id  # nosec
        response = FileUploadCompleteFutureResponse(
            state=FileUploadCompleteState.OK,
            e_tag=new_fmd.entity_tag,
        )
    else:
        # the task is still running
        response = FileUploadCompleteFutureResponse(state=FileUploadCompleteState.NOK)
    return Envelope[FileUploadCompleteFutureResponse](data=response)


@router.delete(
    "/locations/{location_id}/files/{file_id:path}",
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


@router.post(
    "/files/{file_id:path}:soft-copy", response_model=Envelope[FileMetaDataGet]
)
async def copy_as_soft_link(
    query_params: Annotated[StorageQueryParamsBase, Depends()],
    file_id: StorageFileID,
    body: SoftCopyBody,
    request: Request,
):
    dsm = cast(
        SimcoreS3DataManager,
        get_dsm_provider(request.app).get(SimcoreS3DataManager.get_location_id()),
    )
    file_link = await dsm.create_soft_link(query_params.user_id, file_id, body.link_id)

    return Envelope[FileMetaDataGet](data=FileMetaDataGet(**file_link.model_dump()))
