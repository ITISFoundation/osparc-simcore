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
from models_library.groups import Group
from pydantic import TypeAdapter
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
from . import _groups_api
from ._common.exceptions_handlers import handle_plugin_requests_exceptions
from ._common.models import (
    GroupsPathParams,
    GroupsRequestContext,
    GroupsUsersPathParams,
)
from ._common.types import AccessRightsDict
from .exceptions import GroupNotFoundError

_logger = logging.getLogger(__name__)


routes = web.RouteTableDef()


def _to_groupget_model(group: Group, access_rights: AccessRightsDict) -> GroupGet:
    # Fuses both dataset into GroupSet
    return GroupGet.model_validate(
        {
            **group.model_dump(),
            "access_rights": access_rights,
        }
    )


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

    groups_by_type = await _groups_api.list_user_groups_with_read_access(
        request.app, user_id=req_ctx.user_id
    )

    assert groups_by_type.primary
    assert groups_by_type.everyone

    my_product_group = None

    if product.group_id:
        with suppress(GroupNotFoundError):
            # Product is optional
            my_product_group = await _groups_api.get_product_group_for_user(
                app=request.app,
                user_id=req_ctx.user_id,
                product_gid=product.group_id,
            )

    my_groups = MyGroupsGet(
        me=_to_groupget_model(*groups_by_type.primary),
        organizations=[_to_groupget_model(*gi) for gi in groups_by_type.standard],
        all=_to_groupget_model(*groups_by_type.everyone),
        product=_to_groupget_model(*my_product_group) if my_product_group else None,
    )

    return envelope_json_response(my_groups)


#
# Organization groups
#


@routes.get(f"/{API_VTAG}/groups/{{gid}}", name="get_group")
@login_required
@permission_required("groups.read")
@handle_plugin_requests_exceptions
async def get_group(request: web.Request):
    """Get one group details"""
    req_ctx = GroupsRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(GroupsPathParams, request)

    group_info = await _groups_api.get_user_group(
        request.app, user_id=req_ctx.user_id, group_id=path_params.gid
    )

    group = _to_groupget_model(*group_info)
    return envelope_json_response(group)


@routes.post(f"/{API_VTAG}/groups", name="create_group")
@login_required
@permission_required("groups.*")
@handle_plugin_requests_exceptions
async def create_group(request: web.Request):
    """Creates organization groups"""
    req_ctx = GroupsRequestContext.model_validate(request)
    create = await parse_request_body_as(GroupCreate, request)
    new_group = create.model_dump(mode="json", exclude_unset=True)

    created_group = await api.create_user_group(request.app, req_ctx.user_id, new_group)
    assert GroupGet.model_validate(created_group) is not None  # nosec
    return envelope_json_response(created_group, status_cls=web.HTTPCreated)


@routes.patch(f"/{API_VTAG}/groups/{{gid}}", name="update_group")
@login_required
@permission_required("groups.*")
@handle_plugin_requests_exceptions
async def update_group(request: web.Request):
    """Updates organization groups"""
    req_ctx = GroupsRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(GroupsPathParams, request)
    update: GroupUpdate = await parse_request_body_as(GroupUpdate, request)
    new_group_values = update.model_dump(exclude_unset=True)

    group_info = await _groups_api.update_user_group(
        request.app,
        user_id=req_ctx.user_id,
        group_id=path_params.gid,
        new_group_values=new_group_values,
    )

    updated_group = _to_groupget_model(*group_info)
    return envelope_json_response(updated_group)


@routes.delete(f"/{API_VTAG}/groups/{{gid}}", name="delete_group")
@login_required
@permission_required("groups.*")
@handle_plugin_requests_exceptions
async def delete_group(request: web.Request):
    """Deletes organization groups"""
    req_ctx = GroupsRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(GroupsPathParams, request)

    await api.delete_user_group(request.app, req_ctx.user_id, path_params.gid)
    return web.json_response(status=status.HTTP_204_NO_CONTENT)


#
# Users in organization groups (i.e. members of an organization)
#


@routes.get(f"/{API_VTAG}/groups/{{gid}}/users", name="get_all_group_users")
@login_required
@permission_required("groups.*")
@handle_plugin_requests_exceptions
async def get_group_users(request: web.Request):
    """Gets users in organization groups"""
    req_ctx = GroupsRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(GroupsPathParams, request)

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
@handle_plugin_requests_exceptions
async def add_group_user(request: web.Request):
    """
    Adds a user in an organization group
    """
    req_ctx = GroupsRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(GroupsPathParams, request)
    added: GroupUserAdd = await parse_request_body_as(GroupUserAdd, request)

    await api.add_user_in_group(
        request.app,
        req_ctx.user_id,
        path_params.gid,
        new_user_id=added.uid,
        new_user_email=added.email,
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
    user = await api.get_user_in_group(
        request.app, req_ctx.user_id, path_params.gid, path_params.uid
    )
    assert GroupUserGet.model_validate(user) is not None  # nosec
    return envelope_json_response(user)


@routes.patch(f"/{API_VTAG}/groups/{{gid}}/users/{{uid}}", name="update_group_user")
@login_required
@permission_required("groups.*")
@handle_plugin_requests_exceptions
async def update_group_user(request: web.Request):
    req_ctx = GroupsRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(GroupsUsersPathParams, request)
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
@handle_plugin_requests_exceptions
async def delete_group_user(request: web.Request):
    req_ctx = GroupsRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(GroupsUsersPathParams, request)
    await api.delete_user_in_group(
        request.app, req_ctx.user_id, path_params.gid, path_params.uid
    )
    return web.json_response(status=status.HTTP_204_NO_CONTENT)
