# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from typing import Annotated

from fastapi import APIRouter, Depends
from models_library.api_schemas_webserver.catalog import CatalogServiceGet
from models_library.generics import Envelope
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.catalog._controller_rest_tags_handlers import (
    ServicePathParams,
    ServiceTagPathParams,
)
from simcore_service_webserver.tags.schemas import TagGet

router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=[
        "catalog",
        "tags",
    ],
)


@router.get(
    "/catalog/services/{service_key}/{service_version}/tags",
    response_model=Envelope[list[TagGet]],
)
def list_service_tags(
    _path_params: Annotated[ServicePathParams, Depends()],
): ...


@router.post(
    "/catalog/services/{service_key}/{service_version}/tags/{tag_id}:add",
    response_model=Envelope[CatalogServiceGet],
)
def add_service_tag(
    _path_params: Annotated[ServiceTagPathParams, Depends()],
): ...


@router.post(
    "/catalog/services/{service_key}/{service_version}/tags/{tag_id}:remove",
    response_model=Envelope[CatalogServiceGet],
)
def remove_service_tag(
    _path_params: Annotated[ServiceTagPathParams, Depends()],
): ...
