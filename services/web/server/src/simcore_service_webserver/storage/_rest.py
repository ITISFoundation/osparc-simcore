"""Handlers exposed by storage subsystem

Mostly resolves and redirect to storage API
"""

import logging
import urllib.parse
from typing import Any, Final, NamedTuple
from urllib.parse import quote, unquote

from aiohttp import ClientTimeout, web
from models_library.api_schemas_long_running_tasks.tasks import (
    TaskGet,
)
from models_library.api_schemas_rpc_async_jobs.async_jobs import AsyncJobGet
from models_library.api_schemas_storage.storage_schemas import (
    FileUploadCompleteResponse,
    FileUploadCompletionBody,
    FileUploadSchema,
    LinkType,
)
from models_library.api_schemas_webserver.storage import (
    BatchDeletePathsBodyParams,
    DataExportPost,
    StorageLocationPathParams,
    StoragePathComputeSizeParams,
)
from models_library.projects_nodes_io import LocationID
from models_library.utils.change_case import camel_to_snake
from models_library.utils.fastapi_encoders import jsonable_encoder
from pydantic import AnyUrl, BaseModel, ByteSize, TypeAdapter, field_validator
from servicelib.aiohttp import status
from servicelib.aiohttp.client_session import get_client_session
from servicelib.aiohttp.requests_validation import (
    parse_request_body_as,
    parse_request_path_parameters_as,
    parse_request_query_parameters_as,
)
from servicelib.aiohttp.rest_responses import create_data_response
from servicelib.common_headers import X_FORWARDED_PROTO
from servicelib.rabbitmq.rpc_interfaces.storage.paths import (
    compute_path_size as remote_compute_path_size,
)
from servicelib.rabbitmq.rpc_interfaces.storage.paths import (
    delete_paths as remote_delete_paths,
)
from servicelib.rabbitmq.rpc_interfaces.storage.simcore_s3 import start_export_data
from servicelib.request_keys import RQT_USERID_KEY
from servicelib.rest_responses import unwrap_envelope
from yarl import URL

from .._meta import API_VTAG
from ..login.decorators import login_required
from ..models import AuthenticatedRequestContext
from ..rabbitmq import get_rabbitmq_rpc_client
from ..security.decorators import permission_required
from ..tasks._exception_handlers import handle_export_data_exceptions
from .schemas import StorageFileIDStr
from .settings import StorageSettings, get_plugin_settings

log = logging.getLogger(__name__)


def _get_base_storage_url(app: web.Application) -> URL:
    settings: StorageSettings = get_plugin_settings(app)
    return URL(settings.base_url, encoded=True)


def _get_storage_vtag(app: web.Application) -> str:
    settings: StorageSettings = get_plugin_settings(app)
    storage_prefix: str = settings.STORAGE_VTAG
    return storage_prefix


def _to_storage_url(request: web.Request) -> URL:
    """Converts web-api url to storage-api url"""
    userid = request[RQT_USERID_KEY]

    # storage service API endpoint
    url = _get_base_storage_url(request.app)

    basepath_index = 3
    # strip basepath from webserver API path (i.e. webserver api version)
    # >>> URL('http://storage:1234/v5/storage/asdf/').raw_parts[3:]
    suffix = "/".join(request.url.parts[basepath_index:])
    # we need to quote anything before the column, but not the column
    if (column_index := suffix.find(":")) > 0:
        fastapi_encoded_suffix = (
            urllib.parse.quote(suffix[:column_index], safe="/") + suffix[column_index:]
        )
    else:
        fastapi_encoded_suffix = urllib.parse.quote(suffix, safe="/")

    return (
        url.joinpath(fastapi_encoded_suffix, encoded=True)
        .with_query({camel_to_snake(k): v for k, v in request.query.items()})
        .update_query(user_id=userid)
    )


def _from_storage_url(
    request: web.Request, storage_url: AnyUrl, url_encode: str | None
) -> AnyUrl:
    """Converts storage-api url to web-api url"""
    assert storage_url.path  # nosec

    prefix = f"/{_get_storage_vtag(request.app)}"
    converted_url = str(
        request.url.with_path(
            f"/v0/storage{storage_url.path.removeprefix(prefix)}", encoded=True
        ).with_scheme(request.headers.get(X_FORWARDED_PROTO, request.url.scheme))
    )
    if url_encode:
        converted_url = converted_url.replace(
            url_encode, quote(unquote(url_encode), safe="")
        )

    webserver_url: AnyUrl = TypeAdapter(AnyUrl).validate_python(f"{converted_url}")
    return webserver_url


class _ResponseTuple(NamedTuple):
    payload: Any
    status_code: int


async def _forward_request_to_storage(
    request: web.Request,
    method: str,
    body: dict[str, Any] | None = None,
    **kwargs,
) -> _ResponseTuple:
    url = _to_storage_url(request)
    session = get_client_session(request.app)

    async with session.request(
        method.upper(), url, ssl=False, json=body, **kwargs
    ) as resp:
        match resp.status:
            case status.HTTP_422_UNPROCESSABLE_ENTITY:
                raise web.HTTPUnprocessableEntity(
                    reason=await resp.text(), content_type=resp.content_type
                )
            case status.HTTP_404_NOT_FOUND:
                raise web.HTTPNotFound(text=await resp.text())
            case _ if resp.status >= status.HTTP_400_BAD_REQUEST:
                raise web.HTTPError(text=await resp.text())
            case _:
                payload = await resp.json()
                return _ResponseTuple(payload=payload, status_code=resp.status)


# ---------------------------------------------------------------------

routes = web.RouteTableDef()
_storage_prefix = f"/{API_VTAG}/storage"
_storage_locations_prefix = f"{_storage_prefix}/locations"


@routes.get(_storage_locations_prefix, name="list_storage_locations")
@login_required
@permission_required("storage.files.*")
async def list_storage_locations(request: web.Request) -> web.Response:
    payload, resp_status = await _forward_request_to_storage(request, "GET", body=None)
    return create_data_response(payload, status=resp_status)


@routes.get(
    f"{_storage_locations_prefix}/{{location_id}}/paths", name="list_storage_paths"
)
@login_required
@permission_required("storage.files.*")
async def list_paths(request: web.Request) -> web.Response:
    payload, resp_status = await _forward_request_to_storage(request, "GET", body=None)
    return create_data_response(payload, status=resp_status)


def _create_data_response_from_async_job(
    request: web.Request,
    async_job: AsyncJobGet,
) -> web.Response:
    async_job_id = f"{async_job.job_id}"
    return create_data_response(
        TaskGet(
            task_id=async_job_id,
            task_name=async_job_id,
            status_href=f"{request.url.with_path(str(request.app.router['get_async_job_status'].url_for(task_id=async_job_id)))}",
            abort_href=f"{request.url.with_path(str(request.app.router['cancel_async_job'].url_for(task_id=async_job_id)))}",
            result_href=f"{request.url.with_path(str(request.app.router['get_async_job_result'].url_for(task_id=async_job_id)))}",
        ),
        status=status.HTTP_202_ACCEPTED,
    )


@routes.post(
    f"{_storage_locations_prefix}/{{location_id}}/paths/{{path}}:size",
    name="compute_path_size",
)
@login_required
@permission_required("storage.files.*")
async def compute_path_size(request: web.Request) -> web.Response:
    req_ctx = AuthenticatedRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(
        StoragePathComputeSizeParams, request
    )

    rabbitmq_rpc_client = get_rabbitmq_rpc_client(request.app)
    async_job, _ = await remote_compute_path_size(
        rabbitmq_rpc_client,
        user_id=req_ctx.user_id,
        product_name=req_ctx.product_name,
        location_id=path_params.location_id,
        path=path_params.path,
    )

    return _create_data_response_from_async_job(request, async_job)


@routes.post(
    f"{_storage_locations_prefix}/{{location_id}}/-/paths:batchDelete",
    name="batch_delete_paths",
)
@login_required
@permission_required("storage.files.*")
async def batch_delete_paths(request: web.Request):
    req_ctx = AuthenticatedRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(StorageLocationPathParams, request)
    body = await parse_request_body_as(BatchDeletePathsBodyParams, request)

    rabbitmq_rpc_client = get_rabbitmq_rpc_client(request.app)
    async_job, _ = await remote_delete_paths(
        rabbitmq_rpc_client,
        user_id=req_ctx.user_id,
        product_name=req_ctx.product_name,
        location_id=path_params.location_id,
        paths=body.paths,
    )
    return _create_data_response_from_async_job(request, async_job)


@routes.get(
    _storage_locations_prefix + "/{location_id}/datasets", name="list_datasets_metadata"
)
@login_required
@permission_required("storage.files.*")
async def list_datasets_metadata(request: web.Request) -> web.Response:
    class _PathParams(BaseModel):
        location_id: LocationID

    parse_request_path_parameters_as(_PathParams, request)

    payload, resp_status = await _forward_request_to_storage(request, "GET", body=None)
    return create_data_response(payload, status=resp_status)


@routes.get(
    _storage_locations_prefix + "/{location_id}/files/metadata",
    name="get_files_metadata",
)
@login_required
@permission_required("storage.files.*")
async def get_files_metadata(request: web.Request) -> web.Response:
    class _PathParams(BaseModel):
        location_id: LocationID

    parse_request_path_parameters_as(_PathParams, request)

    class _QueryParams(BaseModel):
        uuid_filter: str = ""
        expand_dirs: bool = True

    parse_request_query_parameters_as(_QueryParams, request)

    payload, resp_status = await _forward_request_to_storage(request, "GET", body=None)
    return create_data_response(payload, status=resp_status)


_LIST_ALL_DATASETS_TIMEOUT_S: Final[int] = 60


@routes.get(
    _storage_locations_prefix + "/{location_id}/datasets/{dataset_id}/metadata",
    name="list_dataset_files_metadata",
)
@login_required
@permission_required("storage.files.*")
async def list_dataset_files_metadata(request: web.Request) -> web.Response:
    class _PathParams(BaseModel):
        location_id: LocationID
        dataset_id: str

    parse_request_path_parameters_as(_PathParams, request)

    class _QueryParams(BaseModel):
        uuid_filter: str = ""
        expand_dirs: bool = True

    parse_request_query_parameters_as(_QueryParams, request)

    payload, resp_status = await _forward_request_to_storage(
        request,
        "GET",
        body=None,
        timeout=ClientTimeout(total=_LIST_ALL_DATASETS_TIMEOUT_S),
    )
    return create_data_response(payload, status=resp_status)


@routes.get(
    _storage_locations_prefix + "/{location_id}/files/{file_id}/metadata",
    name="get_file_metadata",
)
@login_required
@permission_required("storage.files.*")
async def get_file_metadata(request: web.Request) -> web.Response:
    class _PathParams(BaseModel):
        location_id: LocationID
        file_id: StorageFileIDStr

    parse_request_path_parameters_as(_PathParams, request)

    payload, resp_status = await _forward_request_to_storage(request, "GET")
    return create_data_response(payload, status=resp_status)


@routes.get(
    _storage_locations_prefix + "/{location_id}/files/{file_id}",
    name="download_file",
)
@login_required
@permission_required("storage.files.*")
async def download_file(request: web.Request) -> web.Response:
    class _PathParams(BaseModel):
        location_id: LocationID
        file_id: StorageFileIDStr

    parse_request_path_parameters_as(_PathParams, request)

    class _QueryParams(BaseModel):
        link_type: LinkType = LinkType.PRESIGNED

    parse_request_query_parameters_as(_QueryParams, request)

    payload, resp_status = await _forward_request_to_storage(request, "GET", body=None)
    return create_data_response(payload, status=resp_status)


@routes.put(
    _storage_locations_prefix + "/{location_id}/files/{file_id}",
    name="upload_file",
)
@login_required
@permission_required("storage.files.*")
async def upload_file(request: web.Request) -> web.Response:
    class _PathParams(BaseModel):
        location_id: LocationID
        file_id: StorageFileIDStr

    path_params = parse_request_path_parameters_as(_PathParams, request)

    class _QueryParams(BaseModel):
        file_size: ByteSize | None = None
        link_type: LinkType = LinkType.PRESIGNED
        is_directory: bool = False

    parse_request_query_parameters_as(_QueryParams, request)

    payload, resp_status = await _forward_request_to_storage(request, "PUT", body=None)
    data, _ = unwrap_envelope(payload)
    file_upload_schema = FileUploadSchema.model_validate(data)
    # NOTE: since storage is fastapi-based it returns file_id not url encoded and aiohttp does not like it
    # /v0/locations/{location_id}/files/{file_id:non-encoded-containing-slashes}:complete --> /v0/storage/locations/{location_id}/files/{file_id:non-encode}:complete
    storage_encoded_file_id = quote(path_params.file_id, safe="/")
    file_upload_schema.links.complete_upload = _from_storage_url(
        request,
        file_upload_schema.links.complete_upload,
        url_encode=storage_encoded_file_id,
    )
    file_upload_schema.links.abort_upload = _from_storage_url(
        request,
        file_upload_schema.links.abort_upload,
        url_encode=storage_encoded_file_id,
    )
    return create_data_response(
        jsonable_encoder(file_upload_schema), status=resp_status
    )


@routes.post(
    _storage_locations_prefix + "/{location_id}/files/{file_id}:complete",
    name="complete_upload_file",
)
@login_required
@permission_required("storage.files.*")
async def complete_upload_file(request: web.Request) -> web.Response:
    class _PathParams(BaseModel):
        location_id: LocationID
        file_id: StorageFileIDStr

    path_params = parse_request_path_parameters_as(_PathParams, request)
    body_item = await parse_request_body_as(FileUploadCompletionBody, request)

    payload, resp_status = await _forward_request_to_storage(
        request, "POST", body=body_item.model_dump()
    )
    data, _ = unwrap_envelope(payload)
    storage_encoded_file_id = quote(path_params.file_id, safe="/")
    file_upload_complete = FileUploadCompleteResponse.model_validate(data)
    file_upload_complete.links.state = _from_storage_url(
        request, file_upload_complete.links.state, url_encode=storage_encoded_file_id
    )
    return create_data_response(
        jsonable_encoder(file_upload_complete), status=resp_status
    )


@routes.post(
    _storage_locations_prefix + "/{location_id}/files/{file_id}:abort",
    name="abort_upload_file",
)
@login_required
@permission_required("storage.files.*")
async def abort_upload_file(request: web.Request) -> web.Response:
    class _PathParams(BaseModel):
        location_id: LocationID
        file_id: StorageFileIDStr

    parse_request_path_parameters_as(_PathParams, request)

    payload, resp_status = await _forward_request_to_storage(request, "POST", body=None)
    return create_data_response(payload, status=resp_status)


@routes.post(
    _storage_locations_prefix
    + "/{location_id}/files/{file_id}:complete/futures/{future_id}",
    name="is_completed_upload_file",
)
@login_required
@permission_required("storage.files.*")
async def is_completed_upload_file(request: web.Request) -> web.Response:
    class _PathParams(BaseModel):
        location_id: LocationID
        file_id: StorageFileIDStr
        future_id: str

    parse_request_path_parameters_as(_PathParams, request)

    payload, resp_status = await _forward_request_to_storage(request, "POST", body=None)
    return create_data_response(payload, status=resp_status)


@routes.delete(
    _storage_locations_prefix + "/{location_id}/files/{file_id}",
    name="delete_file",
)
@login_required
@permission_required("storage.files.*")
async def delete_file(request: web.Request) -> web.Response:
    class _PathParams(BaseModel):
        location_id: LocationID
        file_id: StorageFileIDStr

    parse_request_path_parameters_as(_PathParams, request)

    payload, resp_status = await _forward_request_to_storage(
        request, "DELETE", body=None
    )
    return create_data_response(payload, status=resp_status)


@routes.post(
    _storage_locations_prefix + "/{location_id}/export-data", name="export_data"
)
@login_required
@permission_required("storage.files.*")
@handle_export_data_exceptions
async def export_data(request: web.Request) -> web.Response:
    class _PathParams(BaseModel):
        location_id: LocationID

        @field_validator("location_id")
        @classmethod
        def allow_only_simcore(cls, v: int) -> int:
            if v != 0:
                msg = f"Only simcore (location_id='0'), provided location_id='{v}' is not allowed"
                raise ValueError(msg)
            return v

    rabbitmq_rpc_client = get_rabbitmq_rpc_client(request.app)
    _req_ctx = AuthenticatedRequestContext.model_validate(request)
    _ = parse_request_path_parameters_as(_PathParams, request)
    export_data_post = await parse_request_body_as(
        model_schema_cls=DataExportPost, request=request
    )
    async_job_rpc_get, _ = await start_export_data(
        rabbitmq_rpc_client=rabbitmq_rpc_client,
        user_id=_req_ctx.user_id,
        product_name=_req_ctx.product_name,
        paths_to_export=export_data_post.paths,
    )
    _job_id = f"{async_job_rpc_get.job_id}"
    return create_data_response(
        TaskGet(
            task_id=_job_id,
            task_name=_job_id,
            status_href=f"{request.url.with_path(str(request.app.router['get_async_job_status'].url_for(task_id=_job_id)))}",
            abort_href=f"{request.url.with_path(str(request.app.router['cancel_async_job'].url_for(task_id=_job_id)))}",
            result_href=f"{request.url.with_path(str(request.app.router['get_async_job_result'].url_for(task_id=_job_id)))}",
        ),
        status=status.HTTP_202_ACCEPTED,
    )
