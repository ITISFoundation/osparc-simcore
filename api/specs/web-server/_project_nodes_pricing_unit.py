""" Helper script to automatically generate OAS

This OAS are the source of truth
"""

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from _common import assert_handler_signature_against_model
from fastapi import APIRouter, status
from models_library.api_schemas_webserver.resource_usage import PricingUnitGet
from models_library.generics import Envelope
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.resource_tracker import PricingPlanId, PricingUnitId
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.projects._nodes_handlers import NodePathParams

# from simcore_service_webserver.projects._common_models import ProjectPathParams
from simcore_service_webserver.projects._project_nodes_pricing_unit_handlers import (
    _ProjectNodePricingUnitPathParams,
)

router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=[
        "projects",
    ],
)


@router.get(
    "/projects/{project_id}/nodes/{node_id}/pricing-unit",
    response_model=Envelope[PricingUnitGet | None],
    summary="Get currently connected pricing unit to the project node.",
)
async def get_project_node_pricing_unit(project_id: ProjectID, node_id: NodeID):
    ...


assert_handler_signature_against_model(get_project_node_pricing_unit, NodePathParams)


@router.put(
    "/projects/{project_id}/nodes/{node_id}/pricing-plan/{pricing_plan_id}/pricing-unit/{pricing_unit_id}",
    response_model=Envelope[None],
    summary="Connect pricing unit to the project node (Project node can have only one pricing unit)",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def connect_wallet_to_project(
    project_id: ProjectID,
    node_id: NodeID,
    pricing_plan_id: PricingPlanId,
    pricing_unit_id: PricingUnitId,
):
    ...


assert_handler_signature_against_model(
    connect_wallet_to_project, _ProjectNodePricingUnitPathParams
)
