import asyncio
import logging
import urllib.parse
from typing import cast

from aiohttp import web
from aiohttp.web import RouteTableDef
from common_library.json_serialization import json_dumps
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
from models_library.utils.fastapi_encoders import jsonable_encoder
from pydantic import AnyUrl, ByteSize, TypeAdapter
from servicelib.aiohttp import status
from servicelib.aiohttp.requests_validation import (
    parse_request_body_as,
    parse_request_path_parameters_as,
    parse_request_query_parameters_as,
)

from ._meta import API_VTAG
from .dsm import get_dsm_provider
from .exceptions import FileMetaDataNotFoundError
from .models import (
    CopyAsSoftLinkParams,
    FileDownloadQueryParams,
    FileMetaData,
    FilePathIsUploadCompletedParams,
    FilePathParams,
    FilesMetadataQueryParams,
    FileUploadQueryParams,
    LocationPathParams,
    StorageQueryParamsBase,
    UploadLinks,
)
from .simcore_s3_dsm import SimcoreS3DataManager
from .utils import create_upload_completion_task_name

log = logging.getLogger(__name__)

routes = RouteTableDef()

UPLOAD_TASKS_KEY = f"{__name__}.upload_tasks"


@routes.get(
    f"/{API_VTAG}/locations/{{location_id}}/files/metadata", name="get_files_metadata"
)
async def get_files_metadata(request: web.Request) -> web.Response:
    query_params: FilesMetadataQueryParams = parse_request_query_parameters_as(
        FilesMetadataQueryParams, request
    )
    path_params = parse_request_path_parameters_as(LocationPathParams, request)
    log.debug(
        "received call to get_files_metadata with %s",
        f"{path_params=}, {query_params=}",
    )
    dsm = get_dsm_provider(request.app).get(path_params.location_id)
    data: list[FileMetaData] = await dsm.list_files(
        user_id=query_params.user_id,
        expand_dirs=query_params.expand_dirs,
        uuid_filter=query_params.uuid_filter
        or f"{query_params.project_id or ''}",  # NOTE: https://github.com/ITISFoundation/osparc-issues/issues/1593
        project_id=query_params.project_id,
    )
    return web.json_response(
        {"data": [jsonable_encoder(FileMetaDataGet(**d.model_dump())) for d in data]},
        dumps=json_dumps,
    )


@routes.get(
    f"/{API_VTAG}/locations/{{location_id}}/files/{{file_id}}/metadata",
    name="get_file_metadata",
)
async def get_file_metadata(request: web.Request) -> web.Response:
    query_params: StorageQueryParamsBase = parse_request_query_parameters_as(
        StorageQueryParamsBase, request
    )
    path_params = parse_request_path_parameters_as(FilePathParams, request)
    log.debug(
        "received call to get_file_metadata_dataset with %s",
        f"{path_params=}, {query_params=}",
    )

    dsm = get_dsm_provider(request.app).get(path_params.location_id)
    try:
        data = await dsm.get_file(
            user_id=query_params.user_id,
            file_id=path_params.file_id,
        )
    except FileMetaDataNotFoundError:
        # NOTE: LEGACY compatibility
        # This is what happens Larry... data must be an empty {} or else some old dynamic services will FAIL (sic)
        # Cannot remove until we retire all legacy services
        # https://github.com/ITISFoundation/osparc-simcore/issues/5676
        # https://github.com/ITISFoundation/osparc-simcore/blob/cfdf4f86d844ebb362f4f39e9c6571d561b72897/services/storage/client-sdk/python/simcore_service_storage_sdk/models/file_meta_data_enveloped.py#L34

        return web.json_response(
            {"error": "No result found", "data": {}}, dumps=json_dumps
        )

    if request.headers.get("User-Agent") == "OpenAPI-Generator/0.1.0/python":
        # NOTE: LEGACY compatiblity with API v0.1.0
        # SEE models used in sdk in:
        # https://github.com/ITISFoundation/osparc-simcore/blob/cfdf4f86d844ebb362f4f39e9c6571d561b72897/services/storage/client-sdk/python/simcore_service_storage_sdk/models/file_meta_data_enveloped.py#L34
        # https://github.com/ITISFoundation/osparc-simcore/blob/cfdf4f86d844ebb362f4f39e9c6571d561b72897/services/storage/client-sdk/python/simcore_service_storage_sdk/models/file_meta_data_type.py#L34
        return web.json_response(
            {
                "data": {
                    "file_uuid": data.file_uuid,
                    "location_id": data.location_id,
                    "location": data.location,
                    "bucket_name": data.bucket_name,
                    "object_name": data.object_name,
                    "project_id": data.project_id,
                    "project_name": data.project_name,
                    "node_id": data.node_id,
                    "node_name": data.node_name,
                    "file_name": data.file_name,
                    "user_id": data.user_id,
                    "user_name": None,
                },
                "error": None,
            },
            dumps=json_dumps,
        )

    return web.json_response(
        {"data": jsonable_encoder(FileMetaDataGet(**data.model_dump()))},
        dumps=json_dumps,
    )


@routes.get(
    f"/{API_VTAG}/locations/{{location_id}}/files/{{file_id}}", name="download_file"
)
async def download_file(request: web.Request) -> web.Response:
    query_params: FileDownloadQueryParams = parse_request_query_parameters_as(
        FileDownloadQueryParams, request
    )
    path_params = parse_request_path_parameters_as(FilePathParams, request)
    log.debug(
        "received call to download_file with %s",
        f"{path_params=}, {query_params=}",
    )
    dsm = get_dsm_provider(request.app).get(path_params.location_id)
    link = await dsm.create_file_download_link(
        query_params.user_id, path_params.file_id, query_params.link_type
    )
    return web.json_response({"data": {"link": link}}, dumps=json_dumps)


@routes.put(
    f"/{API_VTAG}/locations/{{location_id}}/files/{{file_id}}", name="upload_file"
)
async def upload_file(request: web.Request) -> web.Response:
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
    query_params: FileUploadQueryParams = parse_request_query_parameters_as(
        FileUploadQueryParams, request
    )
    path_params = parse_request_path_parameters_as(FilePathParams, request)
    log.debug(
        "received call to upload_file with %s",
        f"{path_params=}, {query_params=}",
    )

    dsm = get_dsm_provider(request.app).get(path_params.location_id)
    links: UploadLinks = await dsm.create_file_upload_links(
        user_id=query_params.user_id,
        file_id=path_params.file_id,
        link_type=query_params.link_type,
        file_size_bytes=query_params.file_size or ByteSize(0),
        is_directory=query_params.is_directory,
        sha256_checksum=query_params.sha256_checksum,
    )
    if query_params.is_v1_upload:
        # return v1 response
        assert len(links.urls) == 1  # nosec
        response = {
            "data": {"link": jsonable_encoder(f"{links.urls[0]}", by_alias=True)}
        }
        log.debug("Returning v1 response: %s", response)
        return web.json_response(response, dumps=json_dumps)

    # v2 response
    abort_url = request.url.join(
        request.app.router["abort_upload_file"]
        .url_for(
            location_id=f"{path_params.location_id}",
            file_id=urllib.parse.quote(path_params.file_id, safe=""),
        )
        .with_query(user_id=query_params.user_id)
    )
    complete_url = request.url.join(
        request.app.router["complete_upload_file"]
        .url_for(
            location_id=f"{path_params.location_id}",
            file_id=urllib.parse.quote(path_params.file_id, safe=""),
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
    log.debug("returning v2 response: %s", v2_response)
    return jsonable_encoder(v2_response, by_alias=True)  # type: ignore[no-any-return] # middleware takes care of enveloping


@routes.post(
    f"/{API_VTAG}/locations/{{location_id}}/files/{{file_id}}:abort",
    name="abort_upload_file",
)
async def abort_upload_file(request: web.Request) -> web.Response:
    query_params: StorageQueryParamsBase = parse_request_query_parameters_as(
        StorageQueryParamsBase, request
    )
    path_params = parse_request_path_parameters_as(FilePathParams, request)
    log.debug(
        "received call to abort_upload_file with %s",
        f"{path_params=}, {query_params=}",
    )

    dsm = get_dsm_provider(request.app).get(path_params.location_id)
    await dsm.abort_file_upload(query_params.user_id, path_params.file_id)
    return web.json_response(status=status.HTTP_204_NO_CONTENT)


@routes.post(
    f"/{API_VTAG}/locations/{{location_id}}/files/{{file_id}}:complete",
    name="complete_upload_file",
)
async def complete_upload_file(request: web.Request) -> web.Response:
    query_params: StorageQueryParamsBase = parse_request_query_parameters_as(
        StorageQueryParamsBase, request
    )
    path_params = parse_request_path_parameters_as(FilePathParams, request)
    body = await parse_request_body_as(FileUploadCompletionBody, request)
    log.debug(
        "received call to complete_upload_file with %s",
        f"{path_params=}, {query_params=}",
    )

    dsm = get_dsm_provider(request.app).get(path_params.location_id)
    # NOTE: completing a multipart upload on AWS can take up to several minutes
    # therefore we wait a bit to see if it completes fast and return a 204
    # if it returns slow we return a 202 - Accepted, the client will have to check later
    # for completeness
    task = asyncio.create_task(
        dsm.complete_file_upload(path_params.file_id, query_params.user_id, body.parts),
        name=create_upload_completion_task_name(
            query_params.user_id, path_params.file_id
        ),
    )
    request.app[UPLOAD_TASKS_KEY][task.get_name()] = task
    assert request.transport  # nosec
    ip_addr, port = request.transport.get_extra_info(
        "sockname"
    )  # https://docs.python.org/3/library/asyncio-protocol.html#asyncio.BaseTransport.get_extra_info
    route = (
        request.app.router["is_completed_upload_file"]
        .url_for(
            location_id=f"{path_params.location_id}",
            file_id=urllib.parse.quote(path_params.file_id, safe=""),
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
    return web.json_response(
        status=status.HTTP_202_ACCEPTED,
        data={"data": jsonable_encoder(response, by_alias=True)},
        dumps=json_dumps,
    )


@routes.post(
    f"/{API_VTAG}/locations/{{location_id}}/files/{{file_id}}:complete/futures/{{future_id}}",
    name="is_completed_upload_file",
)
async def is_completed_upload_file(request: web.Request) -> web.Response:
    query_params: StorageQueryParamsBase = parse_request_query_parameters_as(
        StorageQueryParamsBase, request
    )
    path_params = parse_request_path_parameters_as(
        FilePathIsUploadCompletedParams, request
    )
    log.debug(
        "received call to is completed upload file with %s",
        f"{path_params=}, {query_params=}",
    )

    # NOTE: completing a multipart upload on AWS can take up to several minutes
    # therefore we wait a bit to see if it completes fast and return a 204
    # if it returns slow we return a 202 - Accepted, the client will have to check later
    # for completeness
    task_name = create_upload_completion_task_name(
        query_params.user_id, path_params.file_id
    )
    assert task_name == path_params.future_id  # nosec
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
    dsm = get_dsm_provider(request.app).get(path_params.location_id)
    if fmd := await dsm.get_file(
        user_id=query_params.user_id,
        file_id=path_params.file_id,
    ):
        response = FileUploadCompleteFutureResponse(
            state=FileUploadCompleteState.OK, e_tag=fmd.entity_tag
        )
        return jsonable_encoder(response, by_alias=True)  # type: ignore[no-any-return] # middleware takes care of enveloping
    raise web.HTTPNotFound(
        reason="Not found. Upload could not be completed. Please try again and contact support if it fails again."
    )


@routes.delete(
    f"/{API_VTAG}/locations/{{location_id}}/files/{{file_id}}", name="delete_file"
)
async def delete_file(request: web.Request) -> web.Response:
    query_params: StorageQueryParamsBase = parse_request_query_parameters_as(
        StorageQueryParamsBase, request
    )
    path_params = parse_request_path_parameters_as(FilePathParams, request)
    log.debug(
        "received call to delete_file with %s",
        f"{path_params=}, {query_params=}",
    )

    dsm = get_dsm_provider(request.app).get(path_params.location_id)
    await dsm.delete_file(query_params.user_id, path_params.file_id)
    return web.json_response(status=status.HTTP_204_NO_CONTENT)


@routes.post(f"/{API_VTAG}/files/{{file_id}}:soft-copy", name="copy_as_soft_link")
async def copy_as_soft_link(request: web.Request):
    query_params: StorageQueryParamsBase = parse_request_query_parameters_as(
        StorageQueryParamsBase, request
    )
    path_params = parse_request_path_parameters_as(CopyAsSoftLinkParams, request)
    body = await parse_request_body_as(SoftCopyBody, request)
    log.debug(
        "received call to copy_as_soft_link with %s",
        f"{path_params=}, {query_params=}, {body=}",
    )

    dsm = cast(
        SimcoreS3DataManager,
        get_dsm_provider(request.app).get(SimcoreS3DataManager.get_location_id()),
    )
    file_link: FileMetaData = await dsm.create_soft_link(
        query_params.user_id, path_params.file_id, body.link_id
    )

    return jsonable_encoder(FileMetaDataGet(**file_link.model_dump()))
