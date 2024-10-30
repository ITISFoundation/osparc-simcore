# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from models_library.api_schemas_webserver.groups import (
    AllUsersGroups,
    GroupGet,
    GroupPatch,
    GroupUserGet,
)
from models_library.generics import Envelope
from models_library.users import GroupID
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.groups._handlers import (
    GroupUserPatch,
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
    response_model=Envelope[AllUsersGroups],
)
async def list_groups():
    ...


@router.post(
    "/groups",
    response_model=Envelope[GroupGet],
    status_code=status.HTTP_201_CREATED,
)
async def create_group():
    ...


@router.get(
    "/groups/{gid}",
    response_model=Envelope[GroupGet],
)
async def get_group(_p: Annotated[_GroupPathParams, Depends()]):
    ...


@router.patch(
    "/groups/{gid}",
    response_model=Envelope[GroupGet],
)
async def update_group(
    _p: Annotated[_GroupPathParams, Depends()],
    _b: GroupPatch,
):
    ...


@router.delete(
    "/groups/{gid}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_group(_p: Annotated[_GroupPathParams, Depends()]):
    ...


@router.get(
    "/groups/{gid}/users",
    response_model=Envelope[list[GroupUserGet]],
)
async def get_group_users(_p: Annotated[_GroupPathParams, Depends()]):
    ...


@router.post(
    "/groups/{gid}/users",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def add_group_user(
    _p: Annotated[_GroupPathParams, Depends()],
    _new: GroupUserGet,
):
    ...


@router.get(
    "/groups/{gid}/users/{uid}",
    response_model=Envelope[GroupUserGet],
)
async def get_group_user(
    _p: Annotated[_GroupUserPathParams, Depends()],
):
    ...


@router.patch(
    "/groups/{gid}/users/{uid}",
    response_model=Envelope[GroupUserGet],
)
async def update_group_user(
    _p: Annotated[_GroupUserPathParams, Depends()],
    _b: GroupUserPatch,
):
    ...


@router.delete(
    "/groups/{gid}/users/{uid}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_group_user(
    _p: Annotated[_GroupUserPathParams, Depends()],
):
    ...


@router.get(
    "/groups/{gid}/classifiers",
    response_model=Envelope[dict[str, Any]],
)
async def get_group_classifiers(
    gid: GroupID,
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
