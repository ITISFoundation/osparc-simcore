import json
import logging
from typing import cast

from aiohttp import web
from aiohttp.web import RouteTableDef
from models_library.api_schemas_storage import FileMetaDataGet, FoldersBody
from models_library.projects import ProjectID
from models_library.utils.fastapi_encoders import jsonable_encoder
from servicelib.aiohttp.requests_validation import (
    parse_request_body_as,
    parse_request_path_parameters_as,
    parse_request_query_parameters_as,
)
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from settings_library.s3 import S3Settings
from simcore_service_storage.dsm import get_dsm_provider
from simcore_service_storage.simcore_s3_dsm import SimcoreS3DataManager

# Exclusive for simcore-s3 storage -----------------------
from . import sts
from ._meta import api_vtag
from .models import (
    DeleteFolderQueryParams,
    FileMetaData,
    SearchFilesQueryParams,
    SimcoreS3FoldersParams,
    StorageQueryParamsBase,
)

log = logging.getLogger(__name__)

routes = RouteTableDef()


@routes.post(f"/{api_vtag}/simcore-s3:access", name="get_or_create_temporary_s3_access")  # type: ignore
async def get_or_create_temporary_s3_access(request: web.Request):
    query_params = parse_request_query_parameters_as(StorageQueryParamsBase, request)
    log.debug(
        "received call to get_or_create_temporary_s3_access with %s",
        f"{query_params=}",
    )

    s3_settings: S3Settings = await sts.get_or_create_temporary_token_for_user(
        request.app, query_params.user_id
    )
    return {"data": s3_settings.dict()}


@routes.post(f"/{api_vtag}/simcore-s3/folders", name="copy_folders_from_project")  # type: ignore
async def copy_folders_from_project(request: web.Request):
    query_params = parse_request_query_parameters_as(StorageQueryParamsBase, request)
    body = await parse_request_body_as(FoldersBody, request)
    log.debug(
        "received call to create_folders_from_project with %s",
        f"{body=}, {query_params=}",
    )

    dsm = cast(
        SimcoreS3DataManager,
        get_dsm_provider(request.app).get(SimcoreS3DataManager.get_location_id()),
    )
    await dsm.deep_copy_project_simcore_s3(
        query_params.user_id, body.source, body.destination, body.nodes_map
    )

    raise web.HTTPCreated(
        text=json.dumps(body.destination), content_type=MIMETYPE_APPLICATION_JSON
    )


@routes.delete(f"/{api_vtag}/simcore-s3/folders/{{folder_id}}", name="delete_folders_of_project")  # type: ignore
async def delete_folders_of_project(request: web.Request):
    query_params = parse_request_query_parameters_as(DeleteFolderQueryParams, request)
    path_params = parse_request_path_parameters_as(SimcoreS3FoldersParams, request)
    log.debug(
        "received call to delete_folders_of_project with %s",
        f"{path_params=}, {query_params=}",
    )

    dsm = cast(
        SimcoreS3DataManager,
        get_dsm_provider(request.app).get(SimcoreS3DataManager.get_location_id()),
    )
    await dsm.delete_project_simcore_s3(
        query_params.user_id,
        ProjectID(path_params.folder_id),
        query_params.node_id,
    )

    raise web.HTTPNoContent(content_type=MIMETYPE_APPLICATION_JSON)


@routes.post(f"/{api_vtag}/simcore-s3/files/metadata:search", name="search_files_starting_with")  # type: ignore
async def search_files_starting_with(request: web.Request):
    query_params = parse_request_query_parameters_as(SearchFilesQueryParams, request)
    log.debug(
        "received call to search_files_starting_with with %s",
        f"{query_params=}",
    )

    dsm = cast(
        SimcoreS3DataManager,
        get_dsm_provider(request.app).get(SimcoreS3DataManager.get_location_id()),
    )
    data: list[FileMetaData] = await dsm.search_files_starting_with(
        query_params.user_id, prefix=query_params.startswith
    )
    log.debug("Found %d files starting with '%s'", len(data), query_params.startswith)

    py_data = [jsonable_encoder(FileMetaDataGet.from_orm(d)) for d in data]
    return py_data
