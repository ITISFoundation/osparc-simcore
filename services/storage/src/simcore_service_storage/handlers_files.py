import logging
from typing import cast

from aiohttp import web
from aiohttp.web import RouteTableDef
from models_library.api_schemas_storage import FileMetaDataGet, SoftCopyBody
from models_library.utils.fastapi_encoders import jsonable_encoder
from pydantic import AnyUrl
from servicelib.aiohttp.requests_validation import (
    parse_request_body_as,
    parse_request_path_parameters_as,
    parse_request_query_parameters_as,
)
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from simcore_service_storage.simcore_s3_dsm import SimcoreS3DataManager

# Exclusive for simcore-s3 storage -----------------------
from ._meta import api_vtag
from .dsm import get_dsm_provider
from .exceptions import FileMetaDataNotFoundError
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
    dsm = get_dsm_provider(request.app).get(path_params.location_id)
    link = await dsm.create_file_download_link(
        query_params.user_id, path_params.file_id, query_params.link_type
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

    dsm = get_dsm_provider(request.app).get(path_params.location_id)
    link: AnyUrl = await dsm.create_file_upload_link(
        user_id=query_params.user_id,
        file_id=path_params.file_id,
        link_type=query_params.link_type,
    )

    return {"data": {"link": jsonable_encoder(link, by_alias=True)}}


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
