""" Handlers for CRUD operations on /projects/{*}/nodes/{*}/pricing-unit

"""

import functools
import logging

from aiohttp import web
from models_library.api_schemas_webserver.resource_usage import PricingUnitGet
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID, NodeIDStr
from models_library.resource_tracker import PricingPlanId, PricingUnitId
from pydantic import BaseModel, Extra
from pydantic.errors import PydanticErrorMixin
from servicelib.aiohttp.requests_validation import parse_request_path_parameters_as
from servicelib.aiohttp.typing_extension import Handler

from .._meta import API_VTAG
from ..login.decorators import login_required
from ..resource_usage import api as rut_api
from ..security.decorators import permission_required
from ..utils_aiohttp import envelope_json_response
from . import projects_api
from ._common_models import RequestContext
from ._nodes_handlers import NodePathParams
from .db import ProjectDBAPI
from .exceptions import ProjectInvalidRightsError, ProjectNotFoundError

_logger = logging.getLogger(__name__)


class PricingUnitError(PydanticErrorMixin, ValueError):
    ...


class PricingUnitNotFoundError(PricingUnitError):
    msg_template = "Pricing unit not found"


def _handle_projects_nodes_pricing_unit_exceptions(handler: Handler):
    @functools.wraps(handler)
    async def wrapper(request: web.Request) -> web.StreamResponse:
        try:
            return await handler(request)

        except ProjectNotFoundError as exc:
            raise web.HTTPNotFound(reason=f"{exc}") from exc

        except (PricingUnitNotFoundError, ProjectInvalidRightsError) as exc:
            raise web.HTTPForbidden(reason=f"{exc}") from exc

    return wrapper


routes = web.RouteTableDef()


@routes.get(
    f"/{API_VTAG}/projects/{{project_id}}/nodes/{{node_id}}/pricing-unit",
    name="get_project_node_pricing_unit",
)
@login_required
@permission_required("project.wallet.*")
@_handle_projects_nodes_pricing_unit_exceptions
async def get_project_node_pricing_unit(request: web.Request):
    db: ProjectDBAPI = ProjectDBAPI.get_from_app_context(request.app)
    req_ctx = RequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(NodePathParams, request)

    # ensure the project exists
    await projects_api.get_project_for_user(
        request.app,
        project_uuid=f"{path_params.project_id}",
        user_id=req_ctx.user_id,
        include_state=False,
    )

    output = await db.get_project_node_pricing_unit_id(
        path_params.project_id, path_params.node_id
    )
    if output is None:
        return envelope_json_response(None)
    pricing_plan_id, pricing_unit_id = output
    pricing_unit_get = await rut_api.get_pricing_plan_unit(
        request.app, req_ctx.product_name, pricing_plan_id, pricing_unit_id
    )
    webserver_pricing_unit_get = PricingUnitGet(
        pricing_unit_id=pricing_unit_get.pricing_unit_id,
        unit_name=pricing_unit_get.unit_name,
        unit_extra_info=pricing_unit_get.unit_extra_info,  # type: ignore[arg-type]
        current_cost_per_unit=pricing_unit_get.current_cost_per_unit,
        default=pricing_unit_get.default,
    )
    return envelope_json_response(webserver_pricing_unit_get)


class _ProjectNodePricingUnitPathParams(BaseModel):
    project_id: ProjectID
    node_id: NodeID
    pricing_plan_id: PricingPlanId
    pricing_unit_id: PricingUnitId

    class Config:
        extra = Extra.forbid


@routes.put(
    f"/{API_VTAG}/projects/{{project_id}}/nodes/{{node_id}}/pricing-plan/{{pricing_plan_id}}/pricing-unit/{{pricing_unit_id}}",
    name="connect_pricing_unit_to_project_node",
)
@login_required
@permission_required("project.wallet.*")
@_handle_projects_nodes_pricing_unit_exceptions
async def connect_pricing_unit_to_project_node(request: web.Request):
    db: ProjectDBAPI = ProjectDBAPI.get_from_app_context(request.app)
    req_ctx = RequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(
        _ProjectNodePricingUnitPathParams, request
    )

    # ensure the project exists
    project = await projects_api.get_project_for_user(
        request.app,
        project_uuid=f"{path_params.project_id}",
        user_id=req_ctx.user_id,
        include_state=False,
    )

    # Check pricing plan + pricing unit combination
    rut_pricing_unit = await rut_api.get_pricing_plan_unit(
        request.app,
        req_ctx.product_name,
        path_params.pricing_plan_id,
        path_params.pricing_unit_id,
    )
    if rut_pricing_unit.pricing_unit_id != path_params.pricing_unit_id:
        raise PricingUnitNotFoundError

    await db.connect_pricing_unit_to_project_node(
        path_params.project_id,
        path_params.node_id,
        path_params.pricing_plan_id,
        path_params.pricing_unit_id,
    )

    node_data = project["workbench"][NodeIDStr(f"{path_params.node_id}")]

    await projects_api.update_project_node_resources_from_hardware_info(
        request.app,
        user_id=req_ctx.user_id,
        project_id=path_params.project_id,
        node_id=path_params.node_id,
        product_name=req_ctx.product_name,
        hardware_info=rut_pricing_unit.specific_info,
        service_key=node_data["key"],
        service_version=node_data["version"],
    )

    return envelope_json_response(None, web.HTTPNoContent)
