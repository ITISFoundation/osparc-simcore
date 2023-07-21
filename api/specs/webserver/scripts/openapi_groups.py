from fastapi import APIRouter, status
from models_library.generics import Envelope
from models_library.users import GroupID
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.groups.schemas import (
    AllUsersGroups,
    GroupUser,
    UsersGroup,
)

router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=[
        "groups",
    ],
)


@router.get(
    "/groups",
    response_model=Envelope[AllUsersGroups],
    operation_id="list_services",
)
async def list_groups():
    ...


@router.get(
    "/groups/{gid}",
    response_model=Envelope[UsersGroup],
    operation_id="list_services",
)
async def get_group(gid: GroupID):
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
    operation_id="update_group",
)
async def update_group(gid: GroupID, _update: UsersGroup):
    ...


@router.get(
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


#   /v0/groups/{gid}/users:
#     $ref: "./openapi-groups.yaml#/paths/~1groups~1{gid}~1users"

#   /v0/groups/{gid}/users/{uid}:
#     $ref: "./openapi-groups.yaml#/paths/~1groups~1{gid}~1users~1{uid}"

#   /v0/groups/{gid}/classifiers:
#     $ref: "./openapi-groups.yaml#/paths/~1groups~1{gid}~1classifiers"

#   /v0/groups/sparc/classifiers/scicrunch-resources/{rrid}:
#     $ref: "./openapi-groups.yaml#/paths/~1groups~1sparc~1classifiers~1scicrunch-resources~1{rrid}"

#   /v0/groups/sparc/classifiers/scicrunch-resources:search:
#     $ref: "./openapi-groups.yaml#/paths/~1groups~1sparc~1classifiers~1scicrunch-resources:search"
