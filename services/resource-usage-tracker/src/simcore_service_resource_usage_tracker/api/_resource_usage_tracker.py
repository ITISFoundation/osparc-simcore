import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi_pagination.api import create_page
from models_library.api_schemas_webserver.resource_usage import ContainerGet

from ..models.pagination import LimitOffsetPage, LimitOffsetParamsWithDefault
from ..models.resource_tracker_container import ContainersPage
from ..services import resource_tracker_container_service

logger = logging.getLogger(__name__)


router = APIRouter()


@router.get(
    "/usage/containers",
    response_model=LimitOffsetPage[ContainerGet],
    operation_id="list_containers",
    description="Returns a list of tracked containers for a given user and product",
)
async def list_containers(
    page_params: Annotated[LimitOffsetParamsWithDefault, Depends()],
    containers_page: Annotated[
        ContainersPage,
        Depends(resource_tracker_container_service.list_containers),
    ],
):
    page = create_page(
        containers_page.items,
        total=containers_page.total,
        params=page_params,
    )
    return page
