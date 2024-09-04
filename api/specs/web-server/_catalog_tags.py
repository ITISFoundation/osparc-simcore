# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from typing import Annotated

from fastapi import APIRouter, Depends, status
from models_library.generics import Envelope
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.catalog._tags_handlers import (
    ServicePathParams,
    ServiceTagPathParams,
)
from simcore_service_webserver.tags._handlers import TagGet

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
):
    ...


@router.put(
    "/catalog/services/{service_key}/{service_version}/tags/{tag_id}",
    response_model=Envelope[TagGet],
)
def add_service_tag(
    _path_params: Annotated[ServiceTagPathParams, Depends()],
):
    ...


@router.delete(
    "/catalog/services/{service_key}/{service_version}/tags/{tag_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_service_tag(
    _path_params: Annotated[ServiceTagPathParams, Depends()],
):
    ...
