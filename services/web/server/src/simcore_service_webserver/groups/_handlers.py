import functools
import logging
from contextlib import suppress
from typing import Literal

from aiohttp import web
from models_library.api_schemas_webserver.groups import (
    GroupCreate,
    GroupGet,
    GroupUpdate,
    GroupUserAdd,
    GroupUserGet,
    GroupUserUpdate,
    MyGroupsGet,
)
from models_library.users import GroupID, UserID
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter
from servicelib.aiohttp import status
from servicelib.aiohttp.requests_validation import (
    parse_request_body_as,
    parse_request_path_parameters_as,
    parse_request_query_parameters_as,
)
from servicelib.aiohttp.typing_extension import Handler

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
    UserAlreadyInGroupError,
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
            raise web.HTTPNotFound(
                reason=f"User {exc.uid or exc.email} not found"
            ) from exc

        except GroupNotFoundError as exc:
            gid = getattr(exc, "gid", "")
            raise web.HTTPNotFound(reason=f"Group {gid} not found") from exc

        except UserInGroupNotFoundError as exc:
            gid = getattr(exc, "gid", "")
            raise web.HTTPNotFound(reason=f"User not found in group {gid}") from exc

        except UserAlreadyInGroupError as exc:
            gid = getattr(exc, "gid", "")
            raise web.HTTPConflict(reason=f"User is already in group {gid}") from exc

        except UserInsufficientRightsError as exc:
            raise web.HTTPForbidden from exc

    return wrapper


routes = web.RouteTableDef()


@routes.get(f"/{API_VTAG}/groups", name="list_groups")
@login_required
@permission_required("groups.read")
@_handle_groups_exceptions
async def list_groups(request: web.Request):
    """
    List all groups (organizations, primary, everyone and products) I belong to
    """
    product: Product = get_current_product(request)
    req_ctx = _GroupsRequestContext.model_validate(request)

    primary_group, user_groups, all_group = await api.list_user_groups_with_read_access(
        request.app, req_ctx.user_id
    )

    my_group = {
        "me": primary_group,
        "organizations": user_groups,
        "all": all_group,
        "product": None,
    }

    if product.group_id:
        with suppress(GroupNotFoundError):
            # Product is optional
            my_group["product"] = await api.get_product_group_for_user(
                app=request.app,
                user_id=req_ctx.user_id,
                product_gid=product.group_id,
            )

    assert MyGroupsGet.model_validate(my_group) is not None  # nosec
    return envelope_json_response(my_group)


#
# Organization groups
#


class _GroupPathParams(BaseModel):
    gid: GroupID
    model_config = ConfigDict(extra="forbid")


@routes.get(f"/{API_VTAG}/groups/{{gid}}", name="get_group")
@login_required
@permission_required("groups.read")
@_handle_groups_exceptions
async def get_group(request: web.Request):
    """Get one group details"""
    req_ctx = _GroupsRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(_GroupPathParams, request)

    group = await api.get_user_group(request.app, req_ctx.user_id, path_params.gid)
    assert GroupGet.model_validate(group) is not None  # nosec
    return envelope_json_response(group)


@routes.post(f"/{API_VTAG}/groups", name="create_group")
@login_required
@permission_required("groups.*")
@_handle_groups_exceptions
async def create_group(request: web.Request):
    """Creates organization groups"""
    req_ctx = _GroupsRequestContext.model_validate(request)
    create = await parse_request_body_as(GroupCreate, request)
    new_group = create.model_dump(mode="json", exclude_unset=True)

    created_group = await api.create_user_group(request.app, req_ctx.user_id, new_group)
    assert GroupGet.model_validate(created_group) is not None  # nosec
    return envelope_json_response(created_group, status_cls=web.HTTPCreated)


@routes.patch(f"/{API_VTAG}/groups/{{gid}}", name="update_group")
@login_required
@permission_required("groups.*")
@_handle_groups_exceptions
async def update_group(request: web.Request):
    """Updates organization groups"""
    req_ctx = _GroupsRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(_GroupPathParams, request)
    update: GroupUpdate = await parse_request_body_as(GroupUpdate, request)
    new_group_values = update.model_dump(exclude_unset=True)

    updated_group = await api.update_user_group(
        request.app, req_ctx.user_id, path_params.gid, new_group_values
    )
    assert GroupGet.model_validate(updated_group) is not None  # nosec
    return envelope_json_response(updated_group)


@routes.delete(f"/{API_VTAG}/groups/{{gid}}", name="delete_group")
@login_required
@permission_required("groups.*")
@_handle_groups_exceptions
async def delete_group(request: web.Request):
    """Deletes organization groups"""
    req_ctx = _GroupsRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(_GroupPathParams, request)

    await api.delete_user_group(request.app, req_ctx.user_id, path_params.gid)
    return web.json_response(status=status.HTTP_204_NO_CONTENT)


#
# Users in organization groups (i.e. members of an organization)
#


@routes.get(f"/{API_VTAG}/groups/{{gid}}/users", name="get_all_group_users")
@login_required
@permission_required("groups.*")
@_handle_groups_exceptions
async def get_group_users(request: web.Request):
    """Gets users in organization groups"""
    req_ctx = _GroupsRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(_GroupPathParams, request)

    group_user = await api.list_users_in_group(
        request.app, req_ctx.user_id, path_params.gid
    )
    assert (
        TypeAdapter(list[GroupUserGet]).validate_python(group_user) is not None
    )  # nosec
    return envelope_json_response(group_user)


@routes.post(f"/{API_VTAG}/groups/{{gid}}/users", name="add_group_user")
@login_required
@permission_required("groups.*")
@_handle_groups_exceptions
async def add_group_user(request: web.Request):
    """
    Adds a user in an organization group
    """
    req_ctx = _GroupsRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(_GroupPathParams, request)
    added: GroupUserAdd = await parse_request_body_as(GroupUserAdd, request)

    await api.add_user_in_group(
        request.app,
        req_ctx.user_id,
        path_params.gid,
        new_user_id=added.uid,
        new_user_email=added.email,
    )
    return web.json_response(status=status.HTTP_204_NO_CONTENT)


class _GroupUserPathParams(BaseModel):
    gid: GroupID
    uid: UserID
    model_config = ConfigDict(extra="forbid")


@routes.get(f"/{API_VTAG}/groups/{{gid}}/users/{{uid}}", name="get_group_user")
@login_required
@permission_required("groups.*")
@_handle_groups_exceptions
async def get_group_user(request: web.Request):
    """
    Gets specific user in an organization group
    """
    req_ctx = _GroupsRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(_GroupUserPathParams, request)
    user = await api.get_user_in_group(
        request.app, req_ctx.user_id, path_params.gid, path_params.uid
    )
    assert GroupUserGet.model_validate(user) is not None  # nosec
    return envelope_json_response(user)


@routes.patch(f"/{API_VTAG}/groups/{{gid}}/users/{{uid}}", name="update_group_user")
@login_required
@permission_required("groups.*")
@_handle_groups_exceptions
async def update_group_user(request: web.Request):
    req_ctx = _GroupsRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(_GroupUserPathParams, request)
    update: GroupUserUpdate = await parse_request_body_as(GroupUserUpdate, request)

    user = await api.update_user_in_group(
        request.app,
        user_id=req_ctx.user_id,
        gid=path_params.gid,
        the_user_id_in_group=path_params.uid,
        access_rights=update.access_rights.model_dump(),
    )
    assert GroupUserGet.model_validate(user) is not None  # nosec
    return envelope_json_response(user)


@routes.delete(f"/{API_VTAG}/groups/{{gid}}/users/{{uid}}", name="delete_group_user")
@login_required
@permission_required("groups.*")
@_handle_groups_exceptions
async def delete_group_user(request: web.Request):
    req_ctx = _GroupsRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(_GroupUserPathParams, request)
    await api.delete_user_in_group(
        request.app, req_ctx.user_id, path_params.gid, path_params.uid
    )
    return web.json_response(status=status.HTTP_204_NO_CONTENT)


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

    return envelope_json_response(resource.model_dump())


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

    return envelope_json_response(resource.model_dump())


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

    return envelope_json_response([hit.model_dump() for hit in hits])
