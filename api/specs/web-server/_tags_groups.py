# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from typing import Annotated

from fastapi import APIRouter, Depends, status
from models_library.generics import Envelope
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.tags.schemas import (
    TagGet,
    TagGroupCreate,
    TagGroupGet,
    TagGroupPathParams,
    TagPathParams,
)

router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=[
        "tags",
        "groups",
    ],
)


@router.get(
    "/tags/{tag_id}/groups",
    response_model=Envelope[list[TagGroupGet]],
)
async def list_tag_groups(_path_params: Annotated[TagPathParams, Depends()]):
    ...


@router.post(
    "/tags/{tag_id}/groups/{group_id}",
    response_model=Envelope[TagGet],
    status_code=status.HTTP_201_CREATED,
)
async def create_tag_group(
    _path_params: Annotated[TagGroupPathParams, Depends()], _body: TagGroupCreate
):
    """Shares tag `tag_id` with an organization or user with `group_id` providing access-rights to it"""


@router.put(
    "/tags/{tag_id}/groups/{group_id}",
    response_model=Envelope[list[TagGroupGet]],
)
async def replace_tag_groups(
    _path_params: Annotated[TagGroupPathParams, Depends()], _body: TagGroupCreate
):
    """Replace access rights on tag for associated organization or user with `group_id`"""


@router.delete(
    "/tags/{tag_id}/groups/{group_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_tag_group(_path_params: Annotated[TagGroupPathParams, Depends()]):
    """Delete access rights on tag to an associated organization or user with `group_id`"""
