import logging

from aiohttp import web
from aiohttp.web import RouteTableDef
from models_library.api_schemas_storage import FileMetaDataGet
from models_library.utils.fastapi_encoders import jsonable_encoder
from servicelib.aiohttp.requests_validation import (
    parse_request_path_parameters_as,
    parse_request_query_parameters_as,
)
from simcore_service_storage.dsm import get_dsm_provider

# Exclusive for simcore-s3 storage -----------------------
from ._meta import api_vtag
from .models import (
    DatasetMetaData,
    FileMetaData,
    FilesMetadataDatasetPathParams,
    LocationPathParams,
    StorageQueryParamsBase,
)

log = logging.getLogger(__name__)

routes = RouteTableDef()

UPLOAD_TASKS_KEY = f"{__name__}.upload_tasks"


@routes.get(f"/{api_vtag}/locations/{{location_id}}/datasets", name="get_datasets_metadata")  # type: ignore
async def get_datasets_metadata(request: web.Request):
    query_params = parse_request_query_parameters_as(StorageQueryParamsBase, request)
    path_params = parse_request_path_parameters_as(LocationPathParams, request)
    log.debug(
        "received call to get_datasets_metadata with %s",
        f"{path_params=}, {query_params=}",
    )

    dsm = get_dsm_provider(request.app).get(path_params.location_id)
    data: list[DatasetMetaData] = await dsm.list_datasets(query_params.user_id)
    return {"data": data}


@routes.get(f"/{api_vtag}/locations/{{location_id}}/datasets/{{dataset_id}}/metadata", name="get_files_metadata_dataset")  # type: ignore
async def get_files_metadata_dataset(request: web.Request):
    query_params = parse_request_query_parameters_as(StorageQueryParamsBase, request)
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
    )
    py_data = [jsonable_encoder(FileMetaDataGet.from_orm(d)) for d in data]
    return {"data": py_data}
