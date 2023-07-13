""" rest api handlers

- Take into account that part of the API is also needed in the public API so logic
should live in the catalog service in his final version

"""
import logging
import urllib.parse
from typing import Any, Iterator

import orjson
from aiohttp import web
from aiohttp.web import Request, RouteTableDef
from models_library.services import ServiceInput, ServiceOutput
from models_library.services_resources import (
    ServiceResourcesDict,
    ServiceResourcesDictHelpers,
)
from models_library.users import UserID
from pint import UnitRegistry
from pydantic import BaseModel, Extra, Field, validator
from servicelib.aiohttp.requests_validation import (
    handle_validation_as_http_error,
    parse_request_path_parameters_as,
    parse_request_query_parameters_as,
)
from servicelib.rest_constants import RESPONSE_MODEL_POLICY

from .._constants import RQ_PRODUCT_KEY, RQT_USERID_KEY
from .._meta import API_VTAG
from ..login.decorators import login_required
from ..security.decorators import permission_required
from ..utils_aiohttp import envelope_json_response
from . import client
from ._schemas import (
    ServiceInputGet,
    ServiceInputKey,
    ServiceKey,
    ServiceOutputGet,
    ServiceOutputKey,
    ServiceVersion,
    replace_service_input_outputs,
)
from ._units import can_connect

_logger = logging.getLogger(__name__)

VTAG = f"/{API_VTAG}"
routes = RouteTableDef()


class _RequestContext(BaseModel):
    app: web.Application
    user_id: UserID
    product_name: str
    unit_registry: UnitRegistry

    class Config:
        arbitrary_types_allowed = True

    @classmethod
    def create(cls, request: Request) -> "_RequestContext":
        with handle_validation_as_http_error(
            error_msg_template="Invalid request",
            resource_name=request.rel_url.path,
            use_error_v1=True,
        ):
            return cls(
                app=request.app,
                user_id=request[RQT_USERID_KEY],
                product_name=request[RQ_PRODUCT_KEY],
                unit_registry=request.app[UnitRegistry.__name__],
            )


class _ServicePathParams(BaseModel):
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


@routes.get(f"{VTAG}/catalog/services")
@login_required
@permission_required("services.catalog.*")
async def list_services_handler(request: Request):
    req_ctx = _RequestContext.create(request)

    data_array = await list_services(
        request.app,
        user_id=req_ctx.user_id,
        product_name=req_ctx.product_name,
        unit_registry=req_ctx.unit_registry,
    )

    return envelope_json_response(data_array)


@routes.get(f"{VTAG}/catalog/services/{{service_key}}/{{service_version}}")
@login_required
@permission_required("services.catalog.*")
async def get_service_handler(request: Request):
    ctx = _RequestContext.create(request)
    path_params = parse_request_path_parameters_as(_ServicePathParams, request)

    data = await get_service(path_params.service_key, path_params.service_version, ctx)

    return envelope_json_response(data)


@routes.patch(f"{VTAG}/catalog/services/{{service_key}}/{{service_version}}")
@login_required
@permission_required("services.catalog.*")
async def update_service_handler(request: Request):
    ctx = _RequestContext.create(request)
    path_params = parse_request_path_parameters_as(_ServicePathParams, request)
    update_data: dict[str, Any] = await request.json(loads=orjson.loads)

    # Evaluate and return validated model
    data = await update_service(
        path_params.service_key,
        path_params.service_version,
        update_data,
        ctx,
    )

    return envelope_json_response(data)


@routes.get(f"{VTAG}/catalog/services/{{service_key}}/{{service_version}}/inputs")
@login_required
@permission_required("services.catalog.*")
async def list_service_inputs_handler(request: Request):
    ctx = _RequestContext.create(request)
    path_params = parse_request_path_parameters_as(_ServicePathParams, request)

    # Evaluate and return validated model
    response_model = await list_service_inputs(
        path_params.service_key, path_params.service_version, ctx
    )

    data = [m.dict(**RESPONSE_MODEL_POLICY) for m in response_model]
    return envelope_json_response(data)


class _ServiceInputsPathParams(_ServicePathParams):
    input_key: ServiceInputKey


@routes.get(
    f"{VTAG}/catalog/services/{{service_key}}/{{service_version}}/inputs/{{input_key}}"
)
@login_required
@permission_required("services.catalog.*")
async def get_service_input_handler(request: Request):
    ctx = _RequestContext.create(request)
    path_params = parse_request_path_parameters_as(_ServiceInputsPathParams, request)

    # Evaluate and return validated model
    response_model = await get_service_input(
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


@routes.get(f"{VTAG}/catalog/services/{{service_key}}/{{service_version}}/inputs:match")
@login_required
@permission_required("services.catalog.*")
async def get_compatible_inputs_given_source_output_handler(request: Request):
    ctx = _RequestContext.create(request)
    path_params = parse_request_path_parameters_as(_ServicePathParams, request)
    query_params = parse_request_query_parameters_as(_FromServiceOutputParams, request)

    # Evaluate and return validated model
    data = await get_compatible_inputs_given_source_output(
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
)
@login_required
@permission_required("services.catalog.*")
async def list_service_outputs_handler(request: Request):
    ctx = _RequestContext.create(request)
    path_params = parse_request_path_parameters_as(_ServicePathParams, request)

    # Evaluate and return validated model
    response_model = await list_service_outputs(
        path_params.service_key, path_params.service_version, ctx
    )

    data = [m.dict(**RESPONSE_MODEL_POLICY) for m in response_model]
    return envelope_json_response(data)


class _ServiceOutputsPathParams(_ServicePathParams):
    output_key: ServiceOutputKey


@routes.get(
    f"{VTAG}/catalog/services/{{service_key}}/{{service_version}}/outputs/{{output_key}}"
)
@login_required
@permission_required("services.catalog.*")
async def get_service_output_handler(request: Request):
    ctx = _RequestContext.create(request)
    path_params = parse_request_path_parameters_as(_ServiceOutputsPathParams, request)

    # Evaluate and return validated model
    response_model = await get_service_output(
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
    f"{VTAG}/catalog/services/{{service_key}}/{{service_version}}/outputs:match"
)
@login_required
@permission_required("services.catalog.*")
async def get_compatible_outputs_given_target_input_handler(request: Request):
    """
    Filters outputs of this service that match a given service input

    Returns compatible output port of a connected node for a given input
    """
    ctx = _RequestContext.create(request)
    path_params = parse_request_path_parameters_as(_ServicePathParams, request)
    query_params = parse_request_query_parameters_as(_ToServiceInputsParams, request)

    data = await get_compatible_outputs_given_target_input(
        path_params.service_key,
        path_params.service_version,
        query_params.to_service_key,
        query_params.to_service_version,
        query_params.to_input_key,
        ctx,
    )

    return envelope_json_response(data)


@routes.get(f"{VTAG}/catalog/services/{{service_key}}/{{service_version}}/resources")
@login_required
@permission_required("services.catalog.*")
async def get_service_resources_handler(request: Request):
    """
    Filters outputs of this service that match a given service input

    Returns compatible output port of a connected node for a given input
    """
    ctx = _RequestContext.create(request)
    path_params = parse_request_path_parameters_as(_ServicePathParams, request)
    service_resources: ServiceResourcesDict = await client.get_service_resources(
        request.app,
        user_id=ctx.user_id,
        service_key=path_params.service_key,
        service_version=path_params.service_version,
    )

    data = ServiceResourcesDictHelpers.create_jsonable(service_resources)
    return envelope_json_response(data)


# IMPLEMENTATION --------------------------------------------------------------------------------


async def list_services(
    app: web.Application,
    user_id: UserID,
    product_name: str,
    unit_registry: UnitRegistry,
):
    services = await client.get_services_for_user_in_product(
        app, user_id, product_name, only_key_versions=False
    )
    for service in services:
        try:
            replace_service_input_outputs(
                service, unit_registry=unit_registry, **RESPONSE_MODEL_POLICY
            )
        except KeyError:
            # This will limit the effect of a any error in the formatting of
            # service metadata (mostly in label annotations). Otherwise it would
            # completely break all the listing operation. At this moment,
            # a limitation on schema's $ref produced an error that made faiing
            # the full service listing.
            _logger.exception(
                "Failed while processing this %s. "
                "Skipping service from listing. "
                "TIP: check formatting of docker label annotations for inputs/outputs.",
                f"{service=}",
            )
    return services


async def get_service(
    service_key: ServiceKey, service_version: ServiceVersion, ctx: _RequestContext
) -> dict[str, Any]:
    service = await client.get_service(
        ctx.app, ctx.user_id, service_key, service_version, ctx.product_name
    )
    replace_service_input_outputs(
        service, unit_registry=ctx.unit_registry, **RESPONSE_MODEL_POLICY
    )
    return service


async def update_service(
    service_key: ServiceKey,
    service_version: ServiceVersion,
    update_data: dict[str, Any],
    ctx: _RequestContext,
):
    service = await client.update_service(
        ctx.app,
        ctx.user_id,
        service_key,
        service_version,
        ctx.product_name,
        update_data,
    )
    replace_service_input_outputs(
        service, unit_registry=ctx.unit_registry, **RESPONSE_MODEL_POLICY
    )
    return service


async def list_service_inputs(
    service_key: ServiceKey, service_version: ServiceVersion, ctx: _RequestContext
) -> list[ServiceOutputGet]:
    service = await client.get_service(
        ctx.app, ctx.user_id, service_key, service_version, ctx.product_name
    )
    inputs = []
    for input_key in service["inputs"].keys():
        service_input = ServiceInputGet.from_catalog_service_api_model(
            service, input_key
        )
        inputs.append(service_input)
    return inputs


async def get_service_input(
    service_key: ServiceKey,
    service_version: ServiceVersion,
    input_key: ServiceInputKey,
    ctx: _RequestContext,
) -> ServiceInputGet:
    service = await client.get_service(
        ctx.app, ctx.user_id, service_key, service_version, ctx.product_name
    )
    service_input: ServiceInputGet = ServiceInputGet.from_catalog_service_api_model(
        service, input_key
    )

    return service_input


async def get_compatible_inputs_given_source_output(
    service_key: ServiceKey,
    service_version: ServiceVersion,
    from_service_key: ServiceKey,
    from_service_version: ServiceVersion,
    from_output_key: ServiceOutputKey,
    ctx: _RequestContext,
) -> list[ServiceInputKey]:
    """
        Filters inputs of this service that match a given service output

    Returns keys of compatible input ports of the service, provided an output port of
    a connected node.
    """

    # 1 output
    service_output = await get_service_output(
        from_service_key, from_service_version, from_output_key, ctx
    )

    from_output: ServiceOutput = ServiceOutput.construct(
        **service_output.dict(include=ServiceOutput.__fields__.keys())
    )

    # N inputs
    service_inputs = await list_service_inputs(service_key, service_version, ctx)

    def iter_service_inputs() -> Iterator[tuple[ServiceInputKey, ServiceInput]]:
        for service_input in service_inputs:
            yield service_input.key_id, ServiceInput.construct(
                **service_input.dict(include=ServiceInput.__fields__.keys())
            )

    # check
    matches = []
    for key_id, to_input in iter_service_inputs():
        if can_connect(from_output, to_input, units_registry=ctx.unit_registry):
            matches.append(key_id)

    return matches


async def list_service_outputs(
    service_key: ServiceKey,
    service_version: ServiceVersion,
    ctx: _RequestContext,
) -> list[ServiceOutputGet]:
    service = await client.get_service(
        ctx.app, ctx.user_id, service_key, service_version, ctx.product_name
    )

    outputs = []
    for output_key in service["outputs"].keys():
        service_output = ServiceOutputGet.from_catalog_service_api_model(
            service, output_key
        )
        outputs.append(service_output)
    return outputs


async def get_service_output(
    service_key: ServiceKey,
    service_version: ServiceVersion,
    output_key: ServiceOutputKey,
    ctx: _RequestContext,
) -> ServiceOutputGet:
    service = await client.get_service(
        ctx.app, ctx.user_id, service_key, service_version, ctx.product_name
    )
    service_output: ServiceOutputGet = ServiceOutputGet.from_catalog_service_api_model(
        service, output_key
    )

    return service_output


async def get_compatible_outputs_given_target_input(
    service_key: ServiceKey,
    service_version: ServiceVersion,
    to_service_key: ServiceKey,
    to_service_version: ServiceVersion,
    to_input_key: ServiceInputKey,
    ctx: _RequestContext,
) -> list[ServiceOutputKey]:
    # N outputs
    service_outputs = await list_service_outputs(service_key, service_version, ctx)

    def iter_service_outputs() -> Iterator[tuple[ServiceOutputKey, ServiceOutput]]:
        for service_output in service_outputs:
            yield service_output.key_id, ServiceOutput.construct(
                **service_output.dict(include=ServiceOutput.__fields__.keys())
            )

    # 1 input
    service_input = await get_service_input(
        to_service_key, to_service_version, to_input_key, ctx
    )
    to_input: ServiceInput = ServiceInput.construct(
        **service_input.dict(include=ServiceInput.__fields__.keys())
    )

    # check
    matches = []
    for key_id, from_output in iter_service_outputs():
        if can_connect(from_output, to_input, units_registry=ctx.unit_registry):
            matches.append(key_id)

    return matches
