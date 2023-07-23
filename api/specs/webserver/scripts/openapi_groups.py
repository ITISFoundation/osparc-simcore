# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from models_library.generics import Envelope
from models_library.users import GroupID, UserID
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.groups._handlers import _ClassifiersQuery
from simcore_service_webserver.groups.schemas import (
    AllUsersGroups,
    GroupUser,
    UsersGroup,
)
from simcore_service_webserver.scicrunch.models import ResearchResource, ResourceHit

router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=[
        "groups",
    ],
)


@router.get(
    "/groups",
    response_model=Envelope[AllUsersGroups],
    operation_id="list_groups",
)
async def list_groups():
    ...


@router.post(
    "/groups",
    response_model=Envelope[UsersGroup],
    status_code=status.HTTP_201_CREATED,
    operation_id="create_group",
)
async def create_group():
    ...


@router.get(
    "/groups/{gid}",
    response_model=Envelope[UsersGroup],
    operation_id="get_group",
)
async def get_group(gid: GroupID):
    ...


@router.patch(
    "/groups/{gid}",
    response_model=Envelope[UsersGroup],
    operation_id="update_group",
)
async def update_group(gid: GroupID, _update: UsersGroup):
    # FIXME: update type
    ...


@router.delete(
    "/groups/{gid}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="delete_group",
)
async def delete_group(gid: GroupID):
    ...


@router.get(
    "/groups/{gid}/users",
    response_model=Envelope[list[GroupUser]],
    operation_id="get_group_users",
)
async def get_group_users(gid: GroupID):
    ...


@router.post(
    "/groups/{gid}/users",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="add_group_user",
)
async def add_group_user(
    gid: GroupID,
    _new: GroupUser,
):
    ...


@router.get(
    "/groups/{gid}/users/{uid}",
    response_model=Envelope[GroupUser],
    operation_id="get_group_user",
)
async def get_group_user(
    gid: GroupID,
    uid: UserID,
):
    ...


@router.patch(
    "/groups/{gid}/users/{uid}",
    response_model=Envelope[GroupUser],
    operation_id="update_group_user",
)
async def update_group_user(
    gid: GroupID,
    uid: UserID,
    _update: GroupUser,
):
    # FIXME: update type
    ...


@router.delete(
    "/groups/{gid}/users/{uid}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="delete_group_user",
)
async def delete_group_user(
    gid: GroupID,
    uid: UserID,
):
    ...


@router.get(
    "/groups/{gid}/classifiers",
    response_model=Envelope[dict[str, Any]],
    operation_id="get_group_classifiers",
)
async def get_group_classifiers(
    gid: GroupID,
    _query: Annotated[_ClassifiersQuery, Depends()],
):
    ...


@router.get(
    "/groups/sparc/classifiers/scicrunch-resources/{rrid}",
    response_model=Envelope[ResearchResource],
    operation_id="get_scicrunch_resource",
)
async def get_scicrunch_resource(rrid: str):
    ...


@router.post(
    "/groups/sparc/classifiers/scicrunch-resources/{rrid}",
    response_model=Envelope[ResearchResource],
    operation_id="add_scicrunch_resource",
)
async def add_scicrunch_resource(rrid: str):
    ...


@router.get(
    "/groups/sparc/classifiers/scicrunch-resources:search",
    response_model=Envelope[list[ResourceHit]],
    operation_id="search_scicrunch_resources",
)
async def search_scicrunch_resources(guess_name: str):
    ...
