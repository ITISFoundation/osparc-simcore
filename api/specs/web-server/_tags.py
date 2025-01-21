# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from typing import Annotated

from fastapi import APIRouter, Depends, status
from models_library.generics import Envelope
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.tags.schemas import (
    TagCreate,
    TagGet,
    TagPathParams,
    TagUpdate,
)

router = APIRouter(prefix=f"/{API_VTAG}", tags=["tags"])


@router.post(
    "/tags",
    response_model=Envelope[TagGet],
    status_code=status.HTTP_201_CREATED,
)
async def create_tag(_body: TagCreate):
    ...


@router.get(
    "/tags",
    response_model=Envelope[list[TagGet]],
)
async def list_tags():
    ...


@router.patch(
    "/tags/{tag_id}",
    response_model=Envelope[TagGet],
)
async def update_tag(
    _path_params: Annotated[TagPathParams, Depends()], _body: TagUpdate
):
    ...


@router.delete(
    "/tags/{tag_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_tag(_path_params: Annotated[TagPathParams, Depends()]):
    ...
