import logging
from typing import cast

from aiohttp import web
from aiohttp.web import RouteTableDef
from common_library.json_serialization import json_dumps
from models_library.api_schemas_storage import FileMetaDataGet, FoldersBody
from models_library.projects import ProjectID
from models_library.utils.fastapi_encoders import jsonable_encoder
from servicelib.aiohttp import status
from servicelib.aiohttp.long_running_tasks.server import (
    TaskProgress,
    start_long_running_task,
)
from servicelib.aiohttp.requests_validation import (
    parse_request_body_as,
    parse_request_path_parameters_as,
    parse_request_query_parameters_as,
)
from servicelib.logging_utils import log_context
from settings_library.s3 import S3Settings

from . import sts
from ._meta import API_VTAG
from .dsm import get_dsm_provider
from .models import (
    DeleteFolderQueryParams,
    FileMetaData,
    SearchFilesQueryParams,
    SimcoreS3FoldersParams,
    StorageQueryParamsBase,
)
from .simcore_s3_dsm import SimcoreS3DataManager

_logger = logging.getLogger(__name__)

routes = RouteTableDef()


@routes.post(f"/{API_VTAG}/simcore-s3:access", name="get_or_create_temporary_s3_access")
async def get_or_create_temporary_s3_access(request: web.Request) -> web.Response:
    # NOTE: the name of the method is not accurate, these are not temporary at all
    # it returns the credentials of the s3 backend!
    query_params: StorageQueryParamsBase = parse_request_query_parameters_as(
        StorageQueryParamsBase, request
    )
    _logger.debug(
        "received call to get_or_create_temporary_s3_access with %s",
        f"{query_params=}",
    )

    s3_settings: S3Settings = await sts.get_or_create_temporary_token_for_user(
        request.app, query_params.user_id
    )
    return web.json_response({"data": s3_settings.model_dump()}, dumps=json_dumps)


async def _copy_folders_from_project(
    task_progress: TaskProgress,
    app: web.Application,
    query_params: StorageQueryParamsBase,
    body: FoldersBody,
) -> web.Response:
    dsm = cast(
        SimcoreS3DataManager,
        get_dsm_provider(app).get(SimcoreS3DataManager.get_location_id()),
    )
    with log_context(
        _logger,
        logging.INFO,
        msg=f"copying {body.source['uuid']} -> {body.destination['uuid']}",
    ):
        await dsm.deep_copy_project_simcore_s3(
            query_params.user_id,
            body.source,
            body.destination,
            body.nodes_map,
            task_progress=task_progress,
        )

    return web.json_response(
        {"data": jsonable_encoder(body.destination)},
        status=status.HTTP_201_CREATED,
        dumps=json_dumps,
    )


@routes.post(f"/{API_VTAG}/simcore-s3/folders", name="copy_folders_from_project")
async def copy_folders_from_project(request: web.Request) -> web.Response:
    query_params: StorageQueryParamsBase = parse_request_query_parameters_as(
        StorageQueryParamsBase, request
    )
    body = await parse_request_body_as(FoldersBody, request)
    _logger.debug(
        "received call to create_folders_from_project with %s",
        f"{body=}, {query_params=}",
    )
    return await start_long_running_task(
        request,
        _copy_folders_from_project,  # type: ignore[arg-type]
        task_context={},
        app=request.app,
        query_params=query_params,
        body=body,
    )


@routes.delete(
    f"/{API_VTAG}/simcore-s3/folders/{{folder_id}}", name="delete_folders_of_project"
)
async def delete_folders_of_project(request: web.Request) -> web.Response:
    query_params: DeleteFolderQueryParams = parse_request_query_parameters_as(
        DeleteFolderQueryParams, request
    )
    path_params = parse_request_path_parameters_as(SimcoreS3FoldersParams, request)
    _logger.debug(
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

    return web.json_response(status=status.HTTP_204_NO_CONTENT)


@routes.post(f"/{API_VTAG}/simcore-s3/files/metadata:search", name="search_files")
async def search_files(request: web.Request) -> web.Response:
    query_params: SearchFilesQueryParams = parse_request_query_parameters_as(
        SearchFilesQueryParams, request
    )

    _logger.debug(
        "received call to search_files with %s",
        f"{query_params=}",
    )

    dsm = cast(
        SimcoreS3DataManager,
        get_dsm_provider(request.app).get(SimcoreS3DataManager.get_location_id()),
    )

    data: list[FileMetaData] = await dsm.search_owned_files(
        user_id=query_params.user_id,
        file_id_prefix=query_params.startswith,
        sha256_checksum=query_params.sha256_checksum,
        limit=query_params.limit,
        offset=query_params.offset,
    )
    _logger.debug(
        "Found %d files starting with '%s'",
        len(data),
        f"{query_params.startswith=}, {query_params.sha256_checksum=}",
    )

    return web.json_response(
        {"data": [jsonable_encoder(FileMetaDataGet(**d.model_dump())) for d in data]},
        dumps=json_dumps,
    )
