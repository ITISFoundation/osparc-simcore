import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi_pagination.api import create_page
from fastapi_pagination.bases import AbstractPage
from models_library.resource_tracker import ContainerGet
from pydantic import PositiveInt

from ..models.pagination import LimitOffsetPage, LimitOffsetParamsWithDefault
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
    containers_info: tuple[list[ContainerGet], PositiveInt] = Depends(
        resource_tracker_container_service.list_containers
    ),
) -> AbstractPage[ContainerGet]:
    page = create_page(
        containers_info[0],
        containers_info[1],
        page_params,
    )
    return page
