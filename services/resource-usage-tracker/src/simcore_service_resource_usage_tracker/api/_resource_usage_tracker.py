import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi_pagination.api import create_page
from models_library.api_schemas_webserver.resource_usage import ServiceRunGet

from ..models.pagination import LimitOffsetPage, LimitOffsetParamsWithDefault
from ..models.resource_tracker_service_run import ServiceRunPage
from ..services import resource_tracker_service_runs

logger = logging.getLogger(__name__)


router = APIRouter()


@router.get(
    "/usage/services",
    response_model=LimitOffsetPage[ServiceRunGet],
    operation_id="list_usage_services",
    description="Returns a list of tracked containers for a given user and product",
)
async def list_usage_services(
    page_params: Annotated[LimitOffsetParamsWithDefault, Depends()],
    usage_services_page: Annotated[
        ServiceRunPage,
        Depends(resource_tracker_service_runs.list_service_runs),
    ],
):
    page = create_page(
        usage_services_page.items,
        total=usage_services_page.total,
        params=page_params,
    )
    return page
