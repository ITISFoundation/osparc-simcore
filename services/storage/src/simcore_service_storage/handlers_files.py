import logging
import urllib.parse
from typing import Optional

from aiohttp import web
from aiohttp.web import RouteTableDef
from models_library.api_schemas_storage import FileMetaDataGet, LinkType, SoftCopyBody
from models_library.utils.fastapi_encoders import jsonable_encoder
from pydantic import AnyUrl
from servicelib.aiohttp.requests_validation import (
    parse_request_body_as,
    parse_request_path_parameters_as,
    parse_request_query_parameters_as,
)
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON

# Exclusive for simcore-s3 storage -----------------------
from ._meta import api_vtag
from .constants import SIMCORE_S3_ID, SIMCORE_S3_STR
from .models import (
    CopyAsSoftLinkParams,
    FileDownloadQueryParams,
    FileMetaData,
    FilePathParams,
    FilesMetadataQueryParams,
    FileUploadQueryParams,
    LocationPathParams,
    StorageQueryParamsBase,
)
from .utils import get_location_from_id
from .utils_handlers import prepare_storage_manager

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

    dsm = await prepare_storage_manager(
        jsonable_encoder(path_params), jsonable_encoder(query_params), request
    )
    data: list[FileMetaData] = await dsm.list_files(
        user_id=query_params.user_id,
        location=get_location_from_id(path_params.location_id),
        uuid_filter=query_params.uuid_filter,
    )
    py_data = [jsonable_encoder(FileMetaDataGet.from_orm(d)) for d in data]
    return {"data": py_data}


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

    dsm = await prepare_storage_manager(
        jsonable_encoder(path_params), jsonable_encoder(query_params), request
    )

    data: Optional[FileMetaData] = await dsm.list_file(
        user_id=query_params.user_id,
        location=get_location_from_id(path_params.location_id),
        file_id=path_params.file_id,
    )
    # when no metadata is found
    if data is None:
        # NOTE: This is what happens Larry... data must be an empty {} or else some old
        # dynamic services will FAIL (sic)
        return {"error": "No result found", "data": {}}

    return {
        "data": jsonable_encoder(FileMetaDataGet.from_orm(data)),
    }


@routes.get(f"/{api_vtag}/locations/{{location_id}}/files/{{file_id}}", name="download_file")  # type: ignore
async def download_file(request: web.Request):
    query_params = parse_request_query_parameters_as(FileDownloadQueryParams, request)
    path_params = parse_request_path_parameters_as(FilePathParams, request)
    log.debug(
        "received call to download_file with %s",
        f"{path_params=}, {query_params=}",
    )

    if (
        path_params.location_id != SIMCORE_S3_ID
        and query_params.link_type == LinkType.S3
    ):
        raise web.HTTPPreconditionFailed(
            reason=f"Only allowed to fetch s3 link for '{SIMCORE_S3_STR}'"
        )

    dsm = await prepare_storage_manager(
        jsonable_encoder(path_params), jsonable_encoder(query_params), request
    )

    if get_location_from_id(path_params.location_id) == SIMCORE_S3_STR:
        link = await dsm.download_link_s3(
            path_params.file_id, query_params.user_id, query_params.link_type
        )
    else:
        link = await dsm.download_link_datcore(
            query_params.user_id, path_params.file_id
        )

    return {"error": None, "data": {"link": link}}


@routes.put(f"/{api_vtag}/locations/{{location_id}}/files/{{file_id}}", name="upload_file")  # type: ignore
async def upload_file(request: web.Request):
    query_params = parse_request_query_parameters_as(FileUploadQueryParams, request)
    path_params = parse_request_path_parameters_as(FilePathParams, request)

    log.debug(
        "received call to upload_file with %s",
        f"{path_params=}, {query_params=}",
    )

    dsm = await prepare_storage_manager(
        jsonable_encoder(path_params), jsonable_encoder(query_params), request
    )

    link: AnyUrl = await dsm.create_upload_link(
        user_id=query_params.user_id,
        file_id=path_params.file_id,
        link_type=query_params.link_type,
    )

    abort_url = request.url.join(
        request.app.router["abort_upload_file"]
        .url_for(
            location_id=f"{path_params.location_id}",
            file_id=urllib.parse.quote(path_params.file_id, safe=""),
        )
        .with_query(user_id=query_params.user_id)
    )

    response = link

    return {"data": jsonable_encoder(response, by_alias=True)}


@routes.post(f"/{api_vtag}/locations/{{location_id}}/files/{{file_id}}:abort", name="abort_upload_file")  # type: ignore
async def abort_upload_file(request: web.Request):
    query_params = parse_request_query_parameters_as(StorageQueryParamsBase, request)
    path_params = parse_request_path_parameters_as(FilePathParams, request)
    log.debug(
        "received call to abort_upload_file with %s",
        f"{path_params=}, {query_params=}",
    )

    dsm = await prepare_storage_manager(
        jsonable_encoder(path_params), jsonable_encoder(query_params), request
    )
    await dsm.abort_upload(path_params.file_id, query_params.user_id)
    return web.HTTPNoContent(content_type=MIMETYPE_APPLICATION_JSON)


@routes.delete(f"/{api_vtag}/locations/{{location_id}}/files/{{file_id}}", name="delete_file")  # type: ignore
async def delete_file(request: web.Request):
    query_params = parse_request_query_parameters_as(StorageQueryParamsBase, request)
    path_params = parse_request_path_parameters_as(FilePathParams, request)
    log.debug(
        "received call to delete_file with %s",
        f"{path_params=}, {query_params=}",
    )

    dsm = await prepare_storage_manager(
        jsonable_encoder(path_params), jsonable_encoder(query_params), request
    )
    await dsm.delete_file(
        user_id=query_params.user_id,
        location=get_location_from_id(path_params.location_id),
        file_id=path_params.file_id,
    )

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

    dsm = await prepare_storage_manager(
        params={"location_id": SIMCORE_S3_ID},
        query=jsonable_encoder(query_params),
        request=request,
    )
    file_link: FileMetaData = await dsm.create_soft_link(
        query_params.user_id, path_params.file_id, body.link_id
    )

    return jsonable_encoder(FileMetaDataGet.from_orm(file_link))
