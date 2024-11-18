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
    GroupUserGet,
    MyGroupsGet,
)
from models_library.generics import Envelope
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.groups._handlers import (
    GroupUserAdd,
    GroupUserUpdate,
    _ClassifiersQuery,
    _GroupPathParams,
    _GroupUserPathParams,
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
async def get_group(_path: Annotated[_GroupPathParams, Depends()]):
    """
    Get an organization group
    """


@router.patch(
    "/groups/{gid}",
    response_model=Envelope[GroupGet],
)
async def update_group(
    _path: Annotated[_GroupPathParams, Depends()],
    _body: GroupUpdate,
):
    """
    Updates organization groups
    """


@router.delete(
    "/groups/{gid}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_group(_path: Annotated[_GroupPathParams, Depends()]):
    """
    Deletes organization groups
    """


@router.get(
    "/groups/{gid}/users",
    response_model=Envelope[list[GroupUserGet]],
)
async def get_all_group_users(_path: Annotated[_GroupPathParams, Depends()]):
    """
    Gets users in organization groups
    """


@router.post(
    "/groups/{gid}/users",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def add_group_user(
    _path: Annotated[_GroupPathParams, Depends()],
    _body: GroupUserAdd,
):
    """
    Adds a user to an organization group
    """


@router.get(
    "/groups/{gid}/users/{uid}",
    response_model=Envelope[GroupUserGet],
)
async def get_group_user(
    _path: Annotated[_GroupUserPathParams, Depends()],
):
    """
    Gets specific user in an organization group
    """


@router.patch(
    "/groups/{gid}/users/{uid}",
    response_model=Envelope[GroupUserGet],
)
async def update_group_user(
    _path: Annotated[_GroupUserPathParams, Depends()],
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
    _path: Annotated[_GroupUserPathParams, Depends()],
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
    _path: Annotated[_GroupPathParams, Depends()],
    _query: Annotated[_ClassifiersQuery, Depends()],
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
