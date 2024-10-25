import logging

from aiohttp import web
from aiohttp.web import RouteTableDef
from common_library.json_serialization import json_dumps
from models_library.api_schemas_storage import FileMetaDataGet
from models_library.utils.fastapi_encoders import jsonable_encoder
from servicelib.aiohttp.requests_validation import (
    parse_request_path_parameters_as,
    parse_request_query_parameters_as,
)

# Exclusive for simcore-s3 storage -----------------------
from ._meta import API_VTAG
from .dsm import get_dsm_provider
from .models import (
    FileMetaData,
    FilesMetadataDatasetPathParams,
    FilesMetadataDatasetQueryParams,
    LocationPathParams,
    StorageQueryParamsBase,
)

log = logging.getLogger(__name__)

routes = RouteTableDef()

UPLOAD_TASKS_KEY = f"{__name__}.upload_tasks"


@routes.get(
    f"/{API_VTAG}/locations/{{location_id}}/datasets", name="get_datasets_metadata"
)
async def get_datasets_metadata(request: web.Request) -> web.Response:
    query_params: StorageQueryParamsBase = parse_request_query_parameters_as(
        StorageQueryParamsBase, request
    )
    path_params = parse_request_path_parameters_as(LocationPathParams, request)
    log.debug(
        "received call to get_datasets_metadata with %s",
        f"{path_params=}, {query_params=}",
    )

    dsm = get_dsm_provider(request.app).get(path_params.location_id)
    return web.json_response(
        {"data": await dsm.list_datasets(query_params.user_id)}, dumps=json_dumps
    )


@routes.get(
    f"/{API_VTAG}/locations/{{location_id}}/datasets/{{dataset_id}}/metadata",
    name="get_files_metadata_dataset",
)
async def get_files_metadata_dataset(request: web.Request) -> web.Response:
    query_params: FilesMetadataDatasetQueryParams = parse_request_query_parameters_as(
        FilesMetadataDatasetQueryParams, request
    )
    path_params = parse_request_path_parameters_as(
        FilesMetadataDatasetPathParams, request
    )
    log.debug(
        "received call to get_files_metadata_dataset with %s",
        f"{path_params=}, {query_params=}",
    )
    dsm = get_dsm_provider(request.app).get(path_params.location_id)
    data: list[FileMetaData] = await dsm.list_files_in_dataset(
        user_id=query_params.user_id,
        dataset_id=path_params.dataset_id,
        expand_dirs=query_params.expand_dirs,
    )
    return web.json_response(
        {"data": [jsonable_encoder(FileMetaDataGet(**d.model_dump())) for d in data]},
        dumps=json_dumps,
    )
