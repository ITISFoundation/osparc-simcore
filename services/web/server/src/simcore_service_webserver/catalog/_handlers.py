""" rest api handlers

- Take into account that part of the API is also needed in the public API so logic
should live in the catalog service in his final version

"""
import logging
import urllib.parse
from typing import Any, Final

import orjson
from aiohttp.web import Request, RouteTableDef
from models_library.api_schemas_webserver.catalog import (
    ServiceGet,
    ServiceInputKey,
    ServiceOutputKey,
    ServiceUpdate,
)
from models_library.services import ServiceKey, ServiceVersion
from models_library.services_resources import (
    ServiceResourcesDict,
    ServiceResourcesDictHelpers,
)
from pydantic import BaseModel, Extra, Field, parse_obj_as, validator
from servicelib.aiohttp.requests_validation import (
    parse_request_path_parameters_as,
    parse_request_query_parameters_as,
)
from servicelib.rest_constants import RESPONSE_MODEL_POLICY

from .._meta import API_VTAG
from ..login.decorators import login_required
from ..security.decorators import permission_required
from ..utils_aiohttp import envelope_json_response
from . import _api, client
from ._api import CatalogRequestContext

_logger = logging.getLogger(__name__)

VTAG: Final[str] = f"/{API_VTAG}"

routes = RouteTableDef()


class ServicePathParams(BaseModel):
    service_key: ServiceKey
    service_version: ServiceVersion

    class Config:
        allow_population_by_field_name = True
        extra = Extra.forbid

    @validator("service_key", pre=True)
    @classmethod
    def ensure_unquoted(cls, v):
        # NOTE: this is needed as in pytest mode, the aiohttp server does not seem to unquote automatically
        if v is not None:
            return urllib.parse.unquote(v)
        return v


@routes.get(f"{VTAG}/catalog/services", name="list_services")
@login_required
@permission_required("services.catalog.*")
async def list_services(request: Request):
    req_ctx = CatalogRequestContext.create(request)

    data_array = await _api.list_services(
        request.app,
        user_id=req_ctx.user_id,
        product_name=req_ctx.product_name,
        unit_registry=req_ctx.unit_registry,
    )

    # NOTE: this is too heave in devel-mode. Temporary removed
    # assert parse_obj_as(list[ServiceGet], data_array) is not None  # nosec

    return envelope_json_response(data_array)


@routes.get(
    f"{VTAG}/catalog/services/{{service_key}}/{{service_version}}", name="get_service"
)
@login_required
@permission_required("services.catalog.*")
async def get_service(request: Request):
    ctx = CatalogRequestContext.create(request)
    path_params = parse_request_path_parameters_as(ServicePathParams, request)

    data = await _api.get_service(
        path_params.service_key, path_params.service_version, ctx
    )
    assert parse_obj_as(ServiceGet, data) is not None  # nosec
    return envelope_json_response(data)


@routes.patch(
    f"{VTAG}/catalog/services/{{service_key}}/{{service_version}}",
    name="update_service",
)
@login_required
@permission_required("services.catalog.*")
async def update_service(request: Request):
    ctx = CatalogRequestContext.create(request)
    path_params = parse_request_path_parameters_as(ServicePathParams, request)
    update_data: dict[str, Any] = await request.json(loads=orjson.loads)

    assert parse_obj_as(ServiceUpdate, update_data) is not None  # nosec

    # Evaluate and return validated model
    data = await _api.update_service(
        path_params.service_key,
        path_params.service_version,
        update_data,
        ctx,
    )

    assert parse_obj_as(ServiceGet, data) is not None  # nosec
    return envelope_json_response(data)


@routes.get(
    f"{VTAG}/catalog/services/{{service_key}}/{{service_version}}/inputs",
    name="list_service_inputs",
)
@login_required
@permission_required("services.catalog.*")
async def list_service_inputs(request: Request):
    ctx = CatalogRequestContext.create(request)
    path_params = parse_request_path_parameters_as(ServicePathParams, request)

    # Evaluate and return validated model
    response_model = await _api.list_service_inputs(
        path_params.service_key, path_params.service_version, ctx
    )

    data = [m.dict(**RESPONSE_MODEL_POLICY) for m in response_model]
    return envelope_json_response(data)


class _ServiceInputsPathParams(ServicePathParams):
    input_key: ServiceInputKey


@routes.get(
    f"{VTAG}/catalog/services/{{service_key}}/{{service_version}}/inputs/{{input_key}}",
    name="get_service_input",
)
@login_required
@permission_required("services.catalog.*")
async def get_service_input(request: Request):
    ctx = CatalogRequestContext.create(request)
    path_params = parse_request_path_parameters_as(_ServiceInputsPathParams, request)

    # Evaluate and return validated model
    response_model = await _api.get_service_input(
        path_params.service_key,
        path_params.service_version,
        path_params.input_key,
        ctx,
    )

    data = response_model.dict(**RESPONSE_MODEL_POLICY)
    return envelope_json_response(data)


class _FromServiceOutputParams(BaseModel):
    from_service_key: ServiceKey = Field(..., alias="fromService")
    from_service_version: ServiceVersion = Field(..., alias="fromVersion")
    from_output_key: ServiceOutputKey = Field(..., alias="fromOutput")


@routes.get(
    f"{VTAG}/catalog/services/{{service_key}}/{{service_version}}/inputs:match",
    name="get_compatible_inputs_given_source_output",
)
@login_required
@permission_required("services.catalog.*")
async def get_compatible_inputs_given_source_output(request: Request):
    ctx = CatalogRequestContext.create(request)
    path_params = parse_request_path_parameters_as(ServicePathParams, request)
    query_params = parse_request_query_parameters_as(_FromServiceOutputParams, request)

    # Evaluate and return validated model
    data = await _api.get_compatible_inputs_given_source_output(
        path_params.service_key,
        path_params.service_version,
        query_params.from_service_key,
        query_params.from_service_version,
        query_params.from_output_key,
        ctx,
    )

    return envelope_json_response(data)


@routes.get(
    f"{VTAG}/catalog/services/{{service_key}}/{{service_version}}/outputs",
    name="list_service_outputs",
)
@login_required
@permission_required("services.catalog.*")
async def list_service_outputs(request: Request):
    ctx = CatalogRequestContext.create(request)
    path_params = parse_request_path_parameters_as(ServicePathParams, request)

    # Evaluate and return validated model
    response_model = await _api.list_service_outputs(
        path_params.service_key, path_params.service_version, ctx
    )

    data = [m.dict(**RESPONSE_MODEL_POLICY) for m in response_model]
    return envelope_json_response(data)


class _ServiceOutputsPathParams(ServicePathParams):
    output_key: ServiceOutputKey


@routes.get(
    f"{VTAG}/catalog/services/{{service_key}}/{{service_version}}/outputs/{{output_key}}",
    name="get_service_output",
)
@login_required
@permission_required("services.catalog.*")
async def get_service_output(request: Request):
    ctx = CatalogRequestContext.create(request)
    path_params = parse_request_path_parameters_as(_ServiceOutputsPathParams, request)

    # Evaluate and return validated model
    response_model = await _api.get_service_output(
        path_params.service_key,
        path_params.service_version,
        path_params.output_key,
        ctx,
    )

    data = response_model.dict(**RESPONSE_MODEL_POLICY)
    return envelope_json_response(data)


class _ToServiceInputsParams(BaseModel):
    to_service_key: ServiceKey = Field(..., alias="toService")
    to_service_version: ServiceVersion = Field(..., alias="toVersion")
    to_input_key: ServiceInputKey = Field(..., alias="toInput")


@routes.get(
    f"{VTAG}/catalog/services/{{service_key}}/{{service_version}}/outputs:match",
    name="get_compatible_outputs_given_target_input",
)
@login_required
@permission_required("services.catalog.*")
async def get_compatible_outputs_given_target_input(request: Request):
    """
    Filters outputs of this service that match a given service input

    Returns compatible output port of a connected node for a given input
    """
    ctx = CatalogRequestContext.create(request)
    path_params = parse_request_path_parameters_as(ServicePathParams, request)
    query_params = parse_request_query_parameters_as(_ToServiceInputsParams, request)

    data = await _api.get_compatible_outputs_given_target_input(
        path_params.service_key,
        path_params.service_version,
        query_params.to_service_key,
        query_params.to_service_version,
        query_params.to_input_key,
        ctx,
    )

    return envelope_json_response(data)


@routes.get(
    f"{VTAG}/catalog/services/{{service_key}}/{{service_version}}/resources",
    name="get_service_resources",
)
@login_required
@permission_required("services.catalog.*")
async def get_service_resources(request: Request):
    """
    Filters outputs of this service that match a given service input

    Returns compatible output port of a connected node for a given input
    """
    ctx = CatalogRequestContext.create(request)
    path_params = parse_request_path_parameters_as(ServicePathParams, request)
    service_resources: ServiceResourcesDict = await client.get_service_resources(
        request.app,
        user_id=ctx.user_id,
        service_key=path_params.service_key,
        service_version=path_params.service_version,
    )

    data = ServiceResourcesDictHelpers.create_jsonable(service_resources)
    return envelope_json_response(data)
