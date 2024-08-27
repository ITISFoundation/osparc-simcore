import functools
import logging
from contextlib import suppress
from typing import Literal

from aiohttp import web
from models_library.api_schemas_webserver.groups import (
    AllUsersGroups,
    GroupUserGet,
    UsersGroup,
)
from models_library.emails import LowerCaseEmailStr
from models_library.users import GroupID, UserID
from models_library.utils.json_serialization import json_dumps
from pydantic import BaseModel, Extra, Field, parse_obj_as
from servicelib.aiohttp.requests_validation import (
    parse_request_path_parameters_as,
    parse_request_query_parameters_as,
)
from servicelib.aiohttp.typing_extension import Handler
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON

from .._constants import RQ_PRODUCT_KEY, RQT_USERID_KEY
from .._meta import API_VTAG
from ..login.decorators import login_required
from ..products.api import Product, get_current_product
from ..scicrunch.db import ResearchResourceRepository
from ..scicrunch.errors import InvalidRRIDError, ScicrunchError
from ..scicrunch.models import ResearchResource, ResourceHit
from ..scicrunch.service_client import SciCrunch
from ..security.decorators import permission_required
from ..users.exceptions import UserNotFoundError
from ..utils_aiohttp import envelope_json_response
from . import api
from ._classifiers import GroupClassifierRepository, build_rrids_tree_view
from .exceptions import (
    GroupNotFoundError,
    UserInGroupNotFoundError,
    UserInsufficientRightsError,
)

_logger = logging.getLogger(__name__)


class _GroupsRequestContext(BaseModel):
    user_id: UserID = Field(..., alias=RQT_USERID_KEY)  # type: ignore[literal-required]
    product_name: str = Field(..., alias=RQ_PRODUCT_KEY)  # type: ignore[literal-required]


def _handle_groups_exceptions(handler: Handler):
    @functools.wraps(handler)
    async def wrapper(request: web.Request) -> web.StreamResponse:
        try:
            return await handler(request)

        except UserNotFoundError as exc:
            raise web.HTTPNotFound(reason=f"User {exc.uid} not found") from exc

        except GroupNotFoundError as exc:
            raise web.HTTPNotFound(reason=f"Group {exc.gid} not found") from exc

        except UserInGroupNotFoundError as exc:
            raise web.HTTPNotFound(reason=f"User not found in group {exc.gid}") from exc

        except UserInsufficientRightsError as exc:
            raise web.HTTPForbidden from exc

    return wrapper


routes = web.RouteTableDef()


@routes.get(f"/{API_VTAG}/groups", name="list_groups")
@login_required
@permission_required("groups.read")
@_handle_groups_exceptions
async def list_groups(request: web.Request):
    """Lists my groups

    List of the groups I belonged to
    """

    product: Product = get_current_product(request)
    req_ctx = _GroupsRequestContext.parse_obj(request)

    primary_group, user_groups, all_group = await api.list_user_groups_with_read_access(
        request.app, req_ctx.user_id
    )

    result = {
        "me": primary_group,
        "organizations": user_groups,
        "all": all_group,
        "product": None,
    }

    if product.group_id:
        with suppress(GroupNotFoundError):
            result["product"] = await api.get_product_group_for_user(
                app=request.app,
                user_id=req_ctx.user_id,
                product_gid=product.group_id,
            )

    assert parse_obj_as(AllUsersGroups, result) is not None  # nosec
    return result


class _GroupPathParams(BaseModel):
    gid: GroupID

    class Config:
        extra = Extra.forbid


@routes.get(f"/{API_VTAG}/groups/{{gid}}", name="get_group")
@login_required
@permission_required("groups.read")
@_handle_groups_exceptions
async def get_group(request: web.Request):
    """Get one group details"""
    req_ctx = _GroupsRequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(_GroupPathParams, request)

    group = await api.get_user_group(request.app, req_ctx.user_id, path_params.gid)
    assert parse_obj_as(UsersGroup, group) is not None  # nosec
    return group


@routes.post(f"/{API_VTAG}/groups", name="create_group")
@login_required
@permission_required("groups.*")
@_handle_groups_exceptions
async def create_group(request: web.Request):
    """Creates organization groups"""
    req_ctx = _GroupsRequestContext.parse_obj(request)
    new_group = await request.json()

    created_group = await api.create_user_group(request.app, req_ctx.user_id, new_group)
    assert parse_obj_as(UsersGroup, created_group) is not None  # nosec
    raise web.HTTPCreated(
        text=json_dumps({"data": created_group}), content_type=MIMETYPE_APPLICATION_JSON
    )


@routes.patch(f"/{API_VTAG}/groups/{{gid}}", name="update_group")
@login_required
@permission_required("groups.*")
@_handle_groups_exceptions
async def update_group(request: web.Request):
    req_ctx = _GroupsRequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(_GroupPathParams, request)
    new_group_values = await request.json()

    updated_group = await api.update_user_group(
        request.app, req_ctx.user_id, path_params.gid, new_group_values
    )
    assert parse_obj_as(UsersGroup, updated_group) is not None  # nosec
    return envelope_json_response(updated_group)


@routes.delete(f"/{API_VTAG}/groups/{{gid}}", name="delete_group")
@login_required
@permission_required("groups.*")
@_handle_groups_exceptions
async def delete_group(request: web.Request):
    req_ctx = _GroupsRequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(_GroupPathParams, request)

    await api.delete_user_group(request.app, req_ctx.user_id, path_params.gid)
    raise web.HTTPNoContent


@routes.get(f"/{API_VTAG}/groups/{{gid}}/users", name="get_group_users")
@login_required
@permission_required("groups.*")
@_handle_groups_exceptions
async def get_group_users(request: web.Request):
    req_ctx = _GroupsRequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(_GroupPathParams, request)

    group_user = await api.list_users_in_group(
        request.app, req_ctx.user_id, path_params.gid
    )
    assert parse_obj_as(list[GroupUserGet], group_user) is not None  # nosec
    return envelope_json_response(group_user)


@routes.post(f"/{API_VTAG}/groups/{{gid}}/users", name="add_group_user")
@login_required
@permission_required("groups.*")
@_handle_groups_exceptions
async def add_group_user(request: web.Request):
    """
    Adds a user in an organization group
    """
    req_ctx = _GroupsRequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(_GroupPathParams, request)
    new_user_in_group = await request.json()

    assert "uid" in new_user_in_group or "email" in new_user_in_group  # nosec

    new_user_id = new_user_in_group["uid"] if "uid" in new_user_in_group else None
    new_user_email = (
        parse_obj_as(LowerCaseEmailStr, new_user_in_group["email"])
        if "email" in new_user_in_group
        else None
    )

    await api.add_user_in_group(
        request.app,
        req_ctx.user_id,
        path_params.gid,
        new_user_id=new_user_id,
        new_user_email=new_user_email,
    )
    raise web.HTTPNoContent


class _GroupUserPathParams(BaseModel):
    gid: GroupID
    uid: UserID

    class Config:
        extra = Extra.forbid


@routes.get(f"/{API_VTAG}/groups/{{gid}}/users/{{uid}}", name="get_group_user")
@login_required
@permission_required("groups.*")
@_handle_groups_exceptions
async def get_group_user(request: web.Request):
    """
    Gets specific user in group
    """
    req_ctx = _GroupsRequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(_GroupUserPathParams, request)
    user = await api.get_user_in_group(
        request.app, req_ctx.user_id, path_params.gid, path_params.uid
    )
    assert parse_obj_as(GroupUserGet, user) is not None  # nosec
    return envelope_json_response(user)


@routes.patch(f"/{API_VTAG}/groups/{{gid}}/users/{{uid}}", name="update_group_user")
@login_required
@permission_required("groups.*")
@_handle_groups_exceptions
async def update_group_user(request: web.Request):
    """
    Modify specific user in group
    """
    req_ctx = _GroupsRequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(_GroupUserPathParams, request)
    new_values_for_user_in_group = await request.json()
    user = await api.update_user_in_group(
        request.app,
        req_ctx.user_id,
        path_params.gid,
        path_params.uid,
        new_values_for_user_in_group,
    )
    assert parse_obj_as(GroupUserGet, user) is not None  # nosec
    return envelope_json_response(user)


@routes.delete(f"/{API_VTAG}/groups/{{gid}}/users/{{uid}}", name="delete_group_user")
@login_required
@permission_required("groups.*")
@_handle_groups_exceptions
async def delete_group_user(request: web.Request):
    req_ctx = _GroupsRequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(_GroupUserPathParams, request)
    await api.delete_user_in_group(
        request.app, req_ctx.user_id, path_params.gid, path_params.uid
    )
    raise web.HTTPNoContent


#
# Classifiers
#


class _GroupsParams(BaseModel):
    gid: GroupID


class _ClassifiersQuery(BaseModel):
    tree_view: Literal["std"] = "std"


@routes.get(f"/{API_VTAG}/groups/{{gid}}/classifiers", name="get_group_classifiers")
@login_required
@permission_required("groups.*")
async def get_group_classifiers(request: web.Request):
    try:
        path_params = parse_request_path_parameters_as(_GroupsParams, request)
        query_params: _ClassifiersQuery = parse_request_query_parameters_as(
            _ClassifiersQuery, request
        )

        repo = GroupClassifierRepository(request.app)
        if not await repo.group_uses_scicrunch(path_params.gid):
            return await repo.get_classifiers_from_bundle(path_params.gid)

        # otherwise, build dynamic tree with RRIDs
        view = await build_rrids_tree_view(
            request.app, tree_view_mode=query_params.tree_view
        )
    except ScicrunchError:
        view = {}

    return envelope_json_response(view)


def _handle_scicrunch_exceptions(handler: Handler):
    @functools.wraps(handler)
    async def wrapper(request: web.Request) -> web.StreamResponse:
        try:
            return await handler(request)

        except InvalidRRIDError as err:
            raise web.HTTPBadRequest(reason=f"{err}") from err

        except ScicrunchError as err:
            user_msg = "Cannot get RRID since scicrunch.org service is not reachable."
            _logger.exception("%s", user_msg)
            raise web.HTTPServiceUnavailable(reason=user_msg) from err

    return wrapper


@routes.get(
    f"/{API_VTAG}/groups/sparc/classifiers/scicrunch-resources/{{rrid}}",
    name="get_scicrunch_resource",
)
@login_required
@permission_required("groups.*")
@_handle_scicrunch_exceptions
async def get_scicrunch_resource(request: web.Request):
    rrid = request.match_info["rrid"]
    rrid = SciCrunch.validate_identifier(rrid)

    # check if in database first
    repo = ResearchResourceRepository(request.app)
    resource: ResearchResource | None = await repo.get_resource(rrid)
    if not resource:
        # otherwise, request to scicrunch service
        scicrunch = SciCrunch.get_instance(request.app)
        resource = await scicrunch.get_resource_fields(rrid)

    return envelope_json_response(resource.dict())


@routes.post(
    f"/{API_VTAG}/groups/sparc/classifiers/scicrunch-resources/{{rrid}}",
    name="add_scicrunch_resource",
)
@login_required
@permission_required("groups.*")
@_handle_scicrunch_exceptions
async def add_scicrunch_resource(request: web.Request):
    rrid = request.match_info["rrid"]

    # check if exists
    repo = ResearchResourceRepository(request.app)
    resource: ResearchResource | None = await repo.get_resource(rrid)
    if not resource:
        # then request scicrunch service
        scicrunch = SciCrunch.get_instance(request.app)
        resource = await scicrunch.get_resource_fields(rrid)

        # insert new or if exists, then update
        await repo.upsert(resource)

    return envelope_json_response(resource.dict())


@routes.get(
    f"/{API_VTAG}/groups/sparc/classifiers/scicrunch-resources:search",
    name="search_scicrunch_resources",
)
@login_required
@permission_required("groups.*")
@_handle_scicrunch_exceptions
async def search_scicrunch_resources(request: web.Request):
    guess_name = str(request.query["guess_name"]).strip()

    scicrunch = SciCrunch.get_instance(request.app)
    hits: list[ResourceHit] = await scicrunch.search_resource(guess_name)

    return envelope_json_response([hit.dict() for hit in hits])
