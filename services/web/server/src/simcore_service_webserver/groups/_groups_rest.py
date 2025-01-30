import logging
from contextlib import suppress

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
from servicelib.aiohttp import status
from servicelib.aiohttp.requests_validation import (
    parse_request_body_as,
    parse_request_path_parameters_as,
)

from .._meta import API_VTAG
from ..login.decorators import login_required
from ..products.api import Product, get_current_product
from ..security.decorators import permission_required
from ..utils_aiohttp import envelope_json_response
from . import _groups_service
from ._common.exceptions_handlers import handle_plugin_requests_exceptions
from ._common.schemas import (
    GroupsPathParams,
    GroupsRequestContext,
    GroupsUsersPathParams,
)
from .exceptions import GroupNotFoundError

_logger = logging.getLogger(__name__)


routes = web.RouteTableDef()


@routes.get(f"/{API_VTAG}/groups", name="list_groups")
@login_required
@permission_required("groups.read")
@handle_plugin_requests_exceptions
async def list_groups(request: web.Request):
    """
    List all groups (organizations, primary, everyone and products) I belong to
    """
    product: Product = get_current_product(request)
    req_ctx = GroupsRequestContext.model_validate(request)

    groups_by_type = await _groups_service.list_user_groups_with_read_access(
        request.app, user_id=req_ctx.user_id
    )

    assert groups_by_type.primary
    assert groups_by_type.everyone

    my_product_group = None

    if product.group_id:
        with suppress(GroupNotFoundError):
            # Product is optional
            my_product_group = await _groups_service.get_product_group_for_user(
                app=request.app,
                user_id=req_ctx.user_id,
                product_gid=product.group_id,
            )

    my_groups = MyGroupsGet(
        me=GroupGet.from_domain_model(*groups_by_type.primary),
        organizations=[
            GroupGet.from_domain_model(*gi) for gi in groups_by_type.standard
        ],
        all=GroupGet.from_domain_model(*groups_by_type.everyone),
        product=GroupGet.from_domain_model(*my_product_group)
        if my_product_group
        else None,
    )

    return envelope_json_response(my_groups)


#
# ORGANIZATION GROUPS
#


@routes.get(f"/{API_VTAG}/groups/{{gid}}", name="get_group")
@login_required
@permission_required("groups.read")
@handle_plugin_requests_exceptions
async def get_group(request: web.Request):
    """Get one group details"""
    req_ctx = GroupsRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(GroupsPathParams, request)

    group, access_rights = await _groups_service.get_associated_group(
        request.app, user_id=req_ctx.user_id, group_id=path_params.gid
    )

    return envelope_json_response(GroupGet.from_domain_model(group, access_rights))


@routes.post(f"/{API_VTAG}/groups", name="create_group")
@login_required
@permission_required("groups.*")
@handle_plugin_requests_exceptions
async def create_group(request: web.Request):
    """Creates a standard group"""
    req_ctx = GroupsRequestContext.model_validate(request)

    create = await parse_request_body_as(GroupCreate, request)

    group, access_rights = await _groups_service.create_standard_group(
        request.app,
        user_id=req_ctx.user_id,
        create=create.to_domain_model(),
    )

    created_group = GroupGet.from_domain_model(group, access_rights)
    return envelope_json_response(created_group, status_cls=web.HTTPCreated)


@routes.patch(f"/{API_VTAG}/groups/{{gid}}", name="update_group")
@login_required
@permission_required("groups.*")
@handle_plugin_requests_exceptions
async def update_group(request: web.Request):
    """Updates metadata of a standard group"""
    req_ctx = GroupsRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(GroupsPathParams, request)
    update: GroupUpdate = await parse_request_body_as(GroupUpdate, request)

    group, access_rights = await _groups_service.update_standard_group(
        request.app,
        user_id=req_ctx.user_id,
        group_id=path_params.gid,
        update=update.to_domain_model(),
    )

    updated_group = GroupGet.from_domain_model(group, access_rights)
    return envelope_json_response(updated_group)


@routes.delete(f"/{API_VTAG}/groups/{{gid}}", name="delete_group")
@login_required
@permission_required("groups.*")
@handle_plugin_requests_exceptions
async def delete_group(request: web.Request):
    """Deletes a standard group"""
    req_ctx = GroupsRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(GroupsPathParams, request)

    await _groups_service.delete_standard_group(
        request.app, user_id=req_ctx.user_id, group_id=path_params.gid
    )

    return web.json_response(status=status.HTTP_204_NO_CONTENT)


#
# USERS in ORGANIZATION groupS (i.e. members of an organization)
#


@routes.get(f"/{API_VTAG}/groups/{{gid}}/users", name="get_all_group_users")
@login_required
@permission_required("groups.*")
@handle_plugin_requests_exceptions
async def get_all_group_users(request: web.Request):
    """Gets users in organization or primary groups"""
    req_ctx = GroupsRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(GroupsPathParams, request)

    users_in_group = await _groups_service.list_group_members(
        request.app, req_ctx.user_id, path_params.gid
    )

    return envelope_json_response(
        [GroupUserGet.from_domain_model(user) for user in users_in_group]
    )


@routes.post(f"/{API_VTAG}/groups/{{gid}}/users", name="add_group_user")
@login_required
@permission_required("groups.*")
@handle_plugin_requests_exceptions
async def add_group_user(request: web.Request):
    """
    Adds a user in an organization group
    """
    req_ctx = GroupsRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(GroupsPathParams, request)
    added: GroupUserAdd = await parse_request_body_as(GroupUserAdd, request)

    await _groups_service.add_user_in_group(
        request.app,
        req_ctx.user_id,
        path_params.gid,
        new_by_user_id=added.uid,
        new_by_user_name=added.user_name,
        new_by_user_email=added.email,
    )

    return web.json_response(status=status.HTTP_204_NO_CONTENT)


@routes.get(f"/{API_VTAG}/groups/{{gid}}/users/{{uid}}", name="get_group_user")
@login_required
@permission_required("groups.*")
@handle_plugin_requests_exceptions
async def get_group_user(request: web.Request):
    """
    Gets specific user in an organization group
    """
    req_ctx = GroupsRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(GroupsUsersPathParams, request)

    user = await _groups_service.get_group_member(
        request.app, req_ctx.user_id, path_params.gid, path_params.uid
    )

    return envelope_json_response(GroupUserGet.from_domain_model(user))


@routes.patch(f"/{API_VTAG}/groups/{{gid}}/users/{{uid}}", name="update_group_user")
@login_required
@permission_required("groups.*")
@handle_plugin_requests_exceptions
async def update_group_user(request: web.Request):
    req_ctx = GroupsRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(GroupsUsersPathParams, request)
    update: GroupUserUpdate = await parse_request_body_as(GroupUserUpdate, request)

    user = await _groups_service.update_group_member(
        request.app,
        user_id=req_ctx.user_id,
        group_id=path_params.gid,
        the_user_id_in_group=path_params.uid,
        access_rights=update.access_rights.model_dump(mode="json"),  # type: ignore[arg-type]
    )

    return envelope_json_response(GroupUserGet.from_domain_model(user))


@routes.delete(f"/{API_VTAG}/groups/{{gid}}/users/{{uid}}", name="delete_group_user")
@login_required
@permission_required("groups.*")
@handle_plugin_requests_exceptions
async def delete_group_user(request: web.Request):
    req_ctx = GroupsRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(GroupsUsersPathParams, request)
    await _groups_service.delete_group_member(
        request.app, req_ctx.user_id, path_params.gid, path_params.uid
    )

    return web.json_response(status=status.HTTP_204_NO_CONTENT)
