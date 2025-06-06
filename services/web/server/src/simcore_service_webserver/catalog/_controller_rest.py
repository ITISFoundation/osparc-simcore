"""rest api handlers

- Take into account that part of the API is also needed in the public API so logic
should live in the catalog service in his final version

"""

import asyncio
import logging
from typing import Final

from aiohttp import web
from aiohttp.web import Request, RouteTableDef
from models_library.api_schemas_webserver.catalog import (
    CatalogLatestServiceGet,
    CatalogServiceGet,
    CatalogServiceUpdate,
)
from models_library.api_schemas_webserver.resource_usage import PricingPlanGet
from models_library.rest_pagination import Page
from models_library.rest_pagination_utils import paginate_data
from models_library.services_resources import (
    ServiceResourcesDict,
    ServiceResourcesDictHelpers,
)
from servicelib.aiohttp.requests_validation import (
    parse_request_body_as,
    parse_request_path_parameters_as,
    parse_request_query_parameters_as,
)
from servicelib.rest_constants import RESPONSE_MODEL_POLICY

from .._meta import API_VTAG
from ..login.decorators import login_required
from ..resource_usage.service import get_default_service_pricing_plan
from ..security.decorators import permission_required
from ..utils_aiohttp import envelope_json_response
from . import _catalog_rest_client_service, _service
from ._controller_rest_exceptions import (
    handle_plugin_requests_exceptions,
)
from ._controller_rest_schemas import (
    CatalogRequestContext,
    FromServiceOutputQueryParams,
    ListServiceParams,
    ServiceInputsPathParams,
    ServiceOutputsPathParams,
    ServicePathParams,
    ServiceTagPathParams,
    ToServiceInputsQueryParams,
)
from .errors import DefaultPricingUnitForServiceNotFoundError

_logger = logging.getLogger(__name__)

VTAG: Final[str] = f"/{API_VTAG}"
VTAG_DEV: Final[str] = f"{VTAG}/dev"

routes = RouteTableDef()


@routes.get(
    f"{VTAG}/catalog/services/-/latest",
    name="list_services_latest",
)
@login_required
@permission_required("services.catalog.*")
@handle_plugin_requests_exceptions
async def list_services_latest(request: Request):
    request_ctx = CatalogRequestContext.create(request)
    query_params: ListServiceParams = parse_request_query_parameters_as(
        ListServiceParams, request
    )

    page_items, page_meta = await _service.list_latest_services(
        request.app,
        user_id=request_ctx.user_id,
        product_name=request_ctx.product_name,
        unit_registry=request_ctx.unit_registry,
        offset=query_params.offset,
        limit=query_params.limit,
    )

    assert page_meta.limit == query_params.limit  # nosec
    assert page_meta.offset == query_params.offset  # nosec

    page = Page[CatalogLatestServiceGet].model_validate(
        paginate_data(
            chunk=page_items,
            request_url=request.url,
            total=page_meta.total,
            limit=page_meta.limit,
            offset=page_meta.offset,
        )
    )
    return envelope_json_response(page, web.HTTPOk)


@routes.get(
    f"{VTAG}/catalog/services/{{service_key}}/{{service_version}}",
    name="get_service",
)
@login_required
@permission_required("services.catalog.*")
@handle_plugin_requests_exceptions
async def get_service(request: Request):
    request_ctx = CatalogRequestContext.create(request)
    path_params = parse_request_path_parameters_as(ServicePathParams, request)

    assert request_ctx  # nosec
    assert path_params  # nosec

    service = await _service.get_service_v2(
        request.app,
        user_id=request_ctx.user_id,
        product_name=request_ctx.product_name,
        unit_registry=request_ctx.unit_registry,
        service_key=path_params.service_key,
        service_version=path_params.service_version,
    )

    return envelope_json_response(CatalogServiceGet.model_validate(service))


@routes.patch(
    f"{VTAG}/catalog/services/{{service_key}}/{{service_version}}",
    name="update_service",
)
@login_required
@permission_required("services.catalog.*")
@handle_plugin_requests_exceptions
async def update_service(request: Request):
    request_ctx = CatalogRequestContext.create(request)
    path_params = parse_request_path_parameters_as(ServicePathParams, request)
    update: CatalogServiceUpdate = await parse_request_body_as(
        CatalogServiceUpdate, request
    )

    assert request_ctx  # nosec
    assert path_params  # nosec
    assert update  # nosec

    updated = await _service.update_service_v2(
        request.app,
        user_id=request_ctx.user_id,
        product_name=request_ctx.product_name,
        service_key=path_params.service_key,
        service_version=path_params.service_version,
        update_data=update.model_dump(exclude_unset=True),
        unit_registry=request_ctx.unit_registry,
    )

    return envelope_json_response(CatalogServiceGet.model_validate(updated))


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
    response_model = await _service.list_service_inputs(
        path_params.service_key, path_params.service_version, ctx
    )

    data = [m.model_dump(**RESPONSE_MODEL_POLICY) for m in response_model]
    return await asyncio.get_event_loop().run_in_executor(
        None, envelope_json_response, data
    )


@routes.get(
    f"{VTAG}/catalog/services/{{service_key}}/{{service_version}}/inputs/{{input_key}}",
    name="get_service_input",
)
@login_required
@permission_required("services.catalog.*")
async def get_service_input(request: Request):
    ctx = CatalogRequestContext.create(request)
    path_params = parse_request_path_parameters_as(ServiceInputsPathParams, request)

    # Evaluate and return validated model
    response_model = await _service.get_service_input(
        path_params.service_key,
        path_params.service_version,
        path_params.input_key,
        ctx,
    )

    data = response_model.model_dump(**RESPONSE_MODEL_POLICY)
    return await asyncio.get_event_loop().run_in_executor(
        None, envelope_json_response, data
    )


@routes.get(
    f"{VTAG}/catalog/services/{{service_key}}/{{service_version}}/inputs:match",
    name="get_compatible_inputs_given_source_output",
)
@login_required
@permission_required("services.catalog.*")
async def get_compatible_inputs_given_source_output(request: Request):
    ctx = CatalogRequestContext.create(request)
    path_params = parse_request_path_parameters_as(ServicePathParams, request)
    query_params: FromServiceOutputQueryParams = parse_request_query_parameters_as(
        FromServiceOutputQueryParams, request
    )

    # Evaluate and return validated model
    data = await _service.get_compatible_inputs_given_source_output(
        path_params.service_key,
        path_params.service_version,
        query_params.from_service_key,
        query_params.from_service_version,
        query_params.from_output_key,
        ctx,
    )

    return await asyncio.get_event_loop().run_in_executor(
        None, envelope_json_response, data
    )


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
    response_model = await _service.list_service_outputs(
        path_params.service_key, path_params.service_version, ctx
    )

    data = [m.model_dump(**RESPONSE_MODEL_POLICY) for m in response_model]
    return await asyncio.get_event_loop().run_in_executor(
        None, envelope_json_response, data
    )


@routes.get(
    f"{VTAG}/catalog/services/{{service_key}}/{{service_version}}/outputs/{{output_key}}",
    name="get_service_output",
)
@login_required
@permission_required("services.catalog.*")
async def get_service_output(request: Request):
    ctx = CatalogRequestContext.create(request)
    path_params = parse_request_path_parameters_as(ServiceOutputsPathParams, request)

    # Evaluate and return validated model
    response_model = await _service.get_service_output(
        path_params.service_key,
        path_params.service_version,
        path_params.output_key,
        ctx,
    )

    data = response_model.model_dump(**RESPONSE_MODEL_POLICY)
    return await asyncio.get_event_loop().run_in_executor(
        None, envelope_json_response, data
    )


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
    query_params: ToServiceInputsQueryParams = parse_request_query_parameters_as(
        ToServiceInputsQueryParams, request
    )

    data = await _service.get_compatible_outputs_given_target_input(
        path_params.service_key,
        path_params.service_version,
        query_params.to_service_key,
        query_params.to_service_version,
        query_params.to_input_key,
        ctx,
    )

    return await asyncio.get_event_loop().run_in_executor(
        None, envelope_json_response, data
    )


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
    service_resources: ServiceResourcesDict = (
        await _catalog_rest_client_service.get_service_resources(
            request.app,
            user_id=ctx.user_id,
            service_key=path_params.service_key,
            service_version=path_params.service_version,
        )
    )

    data = ServiceResourcesDictHelpers.create_jsonable(service_resources)
    return await asyncio.get_event_loop().run_in_executor(
        None, envelope_json_response, data
    )


@routes.get(
    f"{VTAG}/catalog/services/{{service_key}}/{{service_version}}/pricing-plan",
    name="get_service_pricing_plan",
)
@login_required
@permission_required("services.catalog.*")
@handle_plugin_requests_exceptions
async def get_service_pricing_plan(request: Request):
    ctx = CatalogRequestContext.create(request)
    path_params = parse_request_path_parameters_as(ServicePathParams, request)

    pricing_plan = await get_default_service_pricing_plan(
        app=request.app,
        product_name=ctx.product_name,
        service_key=path_params.service_key,
        service_version=path_params.service_version,
    )
    if pricing_plan.pricing_units is None:
        raise DefaultPricingUnitForServiceNotFoundError(
            service_key=f"{path_params.service_key}",
            service_version=f"{path_params.service_version}",
        )

    return envelope_json_response(
        PricingPlanGet.model_validate(pricing_plan.model_dump())
    )


@routes.get(
    f"/{API_VTAG}/catalog/services/{{service_key}}/{{service_version}}/tags",
    name="list_service_tags",
)
@login_required
@permission_required("service.tag.*")
async def list_service_tags(request: web.Request):
    path_params = parse_request_path_parameters_as(ServicePathParams, request)
    assert path_params  # nosec
    raise NotImplementedError


@routes.post(
    f"/{API_VTAG}/catalog/services/{{service_key}}/{{service_version}}/tags/{{tag_id}}:add",
    name="add_service_tag",
)
@login_required
@permission_required("service.tag.*")
async def add_service_tag(request: web.Request):
    path_params = parse_request_path_parameters_as(ServiceTagPathParams, request)
    assert path_params  # nosec

    # responds with parent's resource to get the current state (as with patch/update)
    raise NotImplementedError


@routes.post(
    f"/{API_VTAG}/catalog/services/{{service_key}}/{{service_version}}/tags/{{tag_id}}:remove",
    name="remove_service_tag",
)
@login_required
@permission_required("service.tag.*")
async def remove_service_tag(request: web.Request):
    path_params = parse_request_path_parameters_as(ServiceTagPathParams, request)
    assert path_params  # nosec

    # responds with parent's resource to get the current state (as with patch/update)
    raise NotImplementedError
