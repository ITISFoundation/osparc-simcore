import asyncio
import logging
import urllib.parse
from typing import cast

from aiohttp import web
from aiohttp.web import RouteTableDef
from models_library.api_schemas_storage import (
    FileMetaDataGet,
    FileUploadCompleteFutureResponse,
    FileUploadCompleteLinks,
    FileUploadCompleteResponse,
    FileUploadCompleteState,
    FileUploadCompletionBody,
    FileUploadLinks,
    FileUploadSchema,
    LinkType,
    SoftCopyBody,
)
from models_library.utils.fastapi_encoders import jsonable_encoder
from pydantic import AnyUrl, parse_obj_as
from servicelib.aiohttp.requests_validation import (
    parse_request_body_as,
    parse_request_path_parameters_as,
    parse_request_query_parameters_as,
)
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON

# Exclusive for simcore-s3 storage -----------------------
from ._meta import api_vtag
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


@routes.get(f"/{api_vtag}/locations/{{location_id}}/files/metadata", name="get_files_metadata")  # type: ignore
async def get_files_metadata(request: web.Request):
    query_params = parse_request_query_parameters_as(FilesMetadataQueryParams, request)
    path_params = parse_request_path_parameters_as(LocationPathParams, request)
    log.debug(
        "received call to get_files_metadata with %s",
        f"{path_params=}, {query_params=}",
    )
    dsm = get_dsm_provider(request.app).get(path_params.location_id)
    data: list[FileMetaData] = await dsm.list_files(
        user_id=query_params.user_id,
        uuid_filter=query_params.uuid_filter,
    )
    return [jsonable_encoder(FileMetaDataGet.from_orm(d)) for d in data]


@routes.get(
    f"/{api_vtag}/locations/{{location_id}}/files/{{file_id}}/metadata",
    name="get_file_metadata",
)  # type: ignore
async def get_file_metadata(request: web.Request):
    query_params = parse_request_query_parameters_as(StorageQueryParamsBase, request)
    path_params = parse_request_path_parameters_as(FilePathParams, request)
    log.debug(
        "received call to get_files_metadata_dataset with %s",
        f"{path_params=}, {query_params=}",
    )

    dsm = get_dsm_provider(request.app).get(path_params.location_id)
    try:
        data = await dsm.get_file(
            user_id=query_params.user_id,
            file_id=path_params.file_id,
        )
    except FileMetaDataNotFoundError:
        # NOTE: This is what happens Larry... data must be an empty {} or else some old
        # dynamic services will FAIL (sic)
        # TODO: once all legacy services are gone, remove the try except, it will default to 404
        return {"error": "No result found", "data": {}}

    return jsonable_encoder(FileMetaDataGet.from_orm(data))


@routes.get(f"/{api_vtag}/locations/{{location_id}}/files/{{file_id}}", name="download_file")  # type: ignore
async def download_file(request: web.Request):
    query_params = parse_request_query_parameters_as(FileDownloadQueryParams, request)
    path_params = parse_request_path_parameters_as(FilePathParams, request)
    log.debug(
        "received call to download_file with %s",
        f"{path_params=}, {query_params=}",
    )
    dsm = get_dsm_provider(request.app).get(path_params.location_id)
    link = await dsm.create_file_download_link(
        query_params.user_id, path_params.file_id, query_params.link_type
    )
    return {"link": link}


@routes.put(f"/{api_vtag}/locations/{{location_id}}/files/{{file_id}}", name="upload_file")  # type: ignore
async def upload_file(request: web.Request):
    """creates upload file links:
    Use-case 1: if query.file_size is 0 or not defined and query.link_type=presigned, returns 1 single presigned link (backward compatibility) (version 0.1)
    Use-case 2: if query.file_size > 0 and query.link_type=presigned, returns 1 or more presigned links, expect client to call "complete_upload" to finish the upload (version 0.2)
    Use-case 3: if query.link_type=s3, returns a s3 link to be used directly with a S3 SDK

    :param request: _description_
    :type request: web.Request
    :return: _description_
    :rtype: _type_
    """
    query_params = parse_request_query_parameters_as(FileUploadQueryParams, request)
    path_params = parse_request_path_parameters_as(FilePathParams, request)

    log.debug(
        "received call to upload_file with %s",
        f"{path_params=}, {query_params=}",
    )

    dsm = get_dsm_provider(request.app).get(path_params.location_id)
    links: UploadLinks = await dsm.create_upload_links(
        user_id=query_params.user_id,
        file_id=path_params.file_id,
        link_type=query_params.link_type,
        file_size_bytes=query_params.file_size,
    )
    if not query_params.file_size and query_params.link_type == LinkType.PRESIGNED:
        assert len(links.urls) == 1  # nosec
        return {"link": jsonable_encoder(links.urls[0], by_alias=True)}

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
    response = FileUploadSchema(
        chunk_size=links.chunk_size,
        urls=links.urls,
        links=FileUploadLinks(
            abort_upload=parse_obj_as(AnyUrl, f"{abort_url}"),
            complete_upload=parse_obj_as(
                AnyUrl,
                f"{complete_url}",
            ),
        ),
    )

    return jsonable_encoder(response, by_alias=True)


@routes.post(f"/{api_vtag}/locations/{{location_id}}/files/{{file_id}}:abort", name="abort_upload_file")  # type: ignore
async def abort_upload_file(request: web.Request):
    query_params = parse_request_query_parameters_as(StorageQueryParamsBase, request)
    path_params = parse_request_path_parameters_as(FilePathParams, request)
    log.debug(
        "received call to abort_upload_file with %s",
        f"{path_params=}, {query_params=}",
    )

    dsm = get_dsm_provider(request.app).get(path_params.location_id)
    await dsm.abort_file_upload(query_params.user_id, path_params.file_id)
    return web.HTTPNoContent(content_type=MIMETYPE_APPLICATION_JSON)


@routes.post(f"/{api_vtag}/locations/{{location_id}}/files/{{file_id}}:complete", name="complete_upload_file")  # type: ignore
async def complete_upload_file(request: web.Request):
    query_params = parse_request_query_parameters_as(StorageQueryParamsBase, request)
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
        dsm.complete_upload(path_params.file_id, query_params.user_id, body.parts),
        name=create_upload_completion_task_name(
            query_params.user_id, path_params.file_id
        ),
    )
    request.app[UPLOAD_TASKS_KEY][task.get_name()] = task
    complete_task_state_url = request.url.join(
        request.app.router["is_completed_upload_file"]
        .url_for(
            location_id=f"{path_params.location_id}",
            file_id=urllib.parse.quote(path_params.file_id, safe=""),
            future_id=task.get_name(),
        )
        .with_query(user_id=query_params.user_id)
    )
    response = FileUploadCompleteResponse(
        links=FileUploadCompleteLinks(
            state=parse_obj_as(AnyUrl, f"{complete_task_state_url}")
        )
    )
    return web.json_response(
        status=web.HTTPAccepted.status_code,
        data={"data": jsonable_encoder(response, by_alias=True)},
    )


@routes.post(f"/{api_vtag}/locations/{{location_id}}/files/{{file_id}}:complete/futures/{{future_id}}", name="is_completed_upload_file")  # type: ignore
async def is_completed_upload_file(request: web.Request):
    query_params = parse_request_query_parameters_as(StorageQueryParamsBase, request)
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
        return jsonable_encoder(response, by_alias=True)
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
        return jsonable_encoder(response, by_alias=True)
    raise web.HTTPNotFound(
        reason="Not found. Upload could not be completed. Please try again and contact support if it fails again."
    )


@routes.delete(f"/{api_vtag}/locations/{{location_id}}/files/{{file_id}}", name="delete_file")  # type: ignore
async def delete_file(request: web.Request):
    query_params = parse_request_query_parameters_as(StorageQueryParamsBase, request)
    path_params = parse_request_path_parameters_as(FilePathParams, request)
    log.debug(
        "received call to delete_file with %s",
        f"{path_params=}, {query_params=}",
    )

    dsm = get_dsm_provider(request.app).get(path_params.location_id)
    await dsm.delete_file(query_params.user_id, path_params.file_id)
    return web.HTTPNoContent(content_type=MIMETYPE_APPLICATION_JSON)


@routes.post(f"/{api_vtag}/files/{{file_id}}:soft-copy", name="copy_as_soft_link")  # type: ignore
async def copy_as_soft_link(request: web.Request):
    query_params = parse_request_query_parameters_as(StorageQueryParamsBase, request)
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

    return jsonable_encoder(FileMetaDataGet.from_orm(file_link))
