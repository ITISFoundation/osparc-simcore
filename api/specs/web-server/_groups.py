# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from models_library.api_schemas_webserver.groups import (
    GroupCreate,
    GroupGet,
    GroupUpdate,
    GroupUserAdd,
    GroupUserGet,
    GroupUserUpdate,
    MyGroupsGet,
)
from models_library.generics import Envelope
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.groups._common.schemas import (
    GroupsClassifiersQuery,
    GroupsPathParams,
    GroupsUsersPathParams,
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
    response_model=Envelope[MyGroupsGet],
)
async def list_groups():
    """
    List all groups (organizations, primary, everyone and products) I belong to
    """


@router.post(
    "/groups",
    response_model=Envelope[GroupGet],
    status_code=status.HTTP_201_CREATED,
)
async def create_group(_body: GroupCreate):
    """
    Creates an organization group
    """


@router.get(
    "/groups/{gid}",
    response_model=Envelope[GroupGet],
)
async def get_group(_path: Annotated[GroupsPathParams, Depends()]):
    """
    Get an organization group
    """


@router.patch(
    "/groups/{gid}",
    response_model=Envelope[GroupGet],
)
async def update_group(
    _path: Annotated[GroupsPathParams, Depends()],
    _body: GroupUpdate,
):
    """
    Updates organization groups
    """


@router.delete(
    "/groups/{gid}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_group(_path: Annotated[GroupsPathParams, Depends()]):
    """
    Deletes organization groups
    """


@router.get(
    "/groups/{gid}/users",
    response_model=Envelope[list[GroupUserGet]],
)
async def get_all_group_users(_path: Annotated[GroupsPathParams, Depends()]):
    """
    Gets users in organization groups
    """


@router.post(
    "/groups/{gid}/users",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def add_group_user(
    _path: Annotated[GroupsPathParams, Depends()],
    _body: GroupUserAdd,
):
    """
    Adds a user to an organization group using their username, user ID, or email (subject to privacy settings)
    """


@router.get(
    "/groups/{gid}/users/{uid}",
    response_model=Envelope[GroupUserGet],
)
async def get_group_user(
    _path: Annotated[GroupsUsersPathParams, Depends()],
):
    """
    Gets specific user in an organization group
    """


@router.patch(
    "/groups/{gid}/users/{uid}",
    response_model=Envelope[GroupUserGet],
)
async def update_group_user(
    _path: Annotated[GroupsUsersPathParams, Depends()],
    _body: GroupUserUpdate,
):
    """
    Updates user (access-rights) to an organization group
    """


@router.delete(
    "/groups/{gid}/users/{uid}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_group_user(
    _path: Annotated[GroupsUsersPathParams, Depends()],
):
    """
    Removes a user from an organization group
    """


#
# Classifiers
#


@router.get(
    "/groups/{gid}/classifiers",
    response_model=Envelope[dict[str, Any]],
)
async def get_group_classifiers(
    _path: Annotated[GroupsPathParams, Depends()],
    _query: Annotated[GroupsClassifiersQuery, Depends()],
):
    ...


@router.get(
    "/groups/sparc/classifiers/scicrunch-resources/{rrid}",
    response_model=Envelope[ResearchResource],
)
async def get_scicrunch_resource(rrid: str):
    ...


@router.post(
    "/groups/sparc/classifiers/scicrunch-resources/{rrid}",
    response_model=Envelope[ResearchResource],
)
async def add_scicrunch_resource(rrid: str):
    ...


@router.get(
    "/groups/sparc/classifiers/scicrunch-resources:search",
    response_model=Envelope[list[ResourceHit]],
)
async def search_scicrunch_resources(guess_name: str):
    ...
