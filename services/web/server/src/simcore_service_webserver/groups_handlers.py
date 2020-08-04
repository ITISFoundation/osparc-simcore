# pylint: disable=no-value-for-parameter

import json
import logging

from aiohttp import web

from . import groups_api
from .groups_exceptions import (
    GroupNotFoundError,
    UserInGroupNotFoundError,
    UserInsufficientRightsError,
)
from .login.decorators import RQT_USERID_KEY, login_required
from .security_decorators import permission_required
from .users_exceptions import UserNotFoundError

logger = logging.getLogger(__name__)


# groups/ ------------------------------------------------------
@login_required
@permission_required("groups.read")
async def list_groups(request: web.Request):
    user_id = request[RQT_USERID_KEY]
    primary_group, user_groups, all_group = await groups_api.list_user_groups(
        request.app, user_id
    )
    return {"me": primary_group, "organizations": user_groups, "all": all_group}


@login_required
@permission_required("groups.read")
async def get_group(request: web.Request):
    user_id = request[RQT_USERID_KEY]
    gid = request.match_info["gid"]
    try:
        return await groups_api.get_user_group(request.app, user_id, gid)
    except GroupNotFoundError:
        raise web.HTTPNotFound(reason=f"Group {gid} not found")


@login_required
@permission_required("groups.*")
async def create_group(request: web.Request):
    user_id = request[RQT_USERID_KEY]
    new_group = await request.json()

    try:
        new_group = await groups_api.create_user_group(request.app, user_id, new_group)
        raise web.HTTPCreated(
            text=json.dumps({"data": new_group}), content_type="application/json"
        )
    except UserNotFoundError:
        raise web.HTTPNotFound(reason=f"User {user_id} not found")


@login_required
@permission_required("groups.*")
async def update_group(request: web.Request):
    user_id = request[RQT_USERID_KEY]
    gid = request.match_info["gid"]
    new_group_values = await request.json()

    try:
        return await groups_api.update_user_group(
            request.app, user_id, gid, new_group_values
        )
    except GroupNotFoundError:
        raise web.HTTPNotFound(reason=f"Group {gid} not found")
    except UserInsufficientRightsError:
        raise web.HTTPForbidden()


@login_required
@permission_required("groups.*")
async def delete_group(request: web.Request):
    user_id = request[RQT_USERID_KEY]
    gid = request.match_info["gid"]
    try:
        await groups_api.delete_user_group(request.app, user_id, gid)
        raise web.HTTPNoContent()
    except GroupNotFoundError:
        raise web.HTTPNotFound(reason=f"Group {gid} not found")
    except UserInsufficientRightsError:
        raise web.HTTPForbidden()


# groups/{gid}/users --------------------------------------------
@login_required
@permission_required("groups.*")
async def get_group_users(request: web.Request):
    user_id = request[RQT_USERID_KEY]
    gid = request.match_info["gid"]
    try:
        return await groups_api.list_users_in_group(request.app, user_id, gid)
    except GroupNotFoundError:
        raise web.HTTPNotFound(reason=f"Group {gid} not found")
    except UserInsufficientRightsError:
        raise web.HTTPForbidden()


@login_required
@permission_required("groups.*")
async def add_group_user(request: web.Request):
    user_id = request[RQT_USERID_KEY]
    gid = request.match_info["gid"]
    new_user_in_group = await request.json()
    # TODO: validate!!
    assert "uid" in new_user_in_group or "email" in new_user_in_group  # nosec
    try:
        new_user_id = new_user_in_group["uid"] if "uid" in new_user_in_group else None
        new_user_email = (
            new_user_in_group["email"] if "email" in new_user_in_group else None
        )

        await groups_api.add_user_in_group(
            request.app,
            user_id,
            gid,
            new_user_id=new_user_id,
            new_user_email=new_user_email,
        )
        raise web.HTTPNoContent()
    except GroupNotFoundError:
        raise web.HTTPNotFound(reason=f"Group {gid} not found")
    except UserInGroupNotFoundError:
        raise web.HTTPNotFound(reason=f"User not found in group {gid}")
    except UserInsufficientRightsError:
        raise web.HTTPForbidden()


@login_required
@permission_required("groups.*")
async def get_group_user(request: web.Request):
    user_id = request[RQT_USERID_KEY]
    gid = request.match_info["gid"]
    the_user_id_in_group = request.match_info["uid"]
    try:
        return await groups_api.get_user_in_group(
            request.app, user_id, gid, the_user_id_in_group
        )
    except GroupNotFoundError:
        raise web.HTTPNotFound(reason=f"Group {gid} not found")
    except UserInGroupNotFoundError:
        raise web.HTTPNotFound(reason=f"User {the_user_id_in_group} not found")
    except UserInsufficientRightsError:
        raise web.HTTPForbidden()


@login_required
@permission_required("groups.*")
async def update_group_user(request: web.Request):
    user_id = request[RQT_USERID_KEY]
    gid = request.match_info["gid"]
    the_user_id_in_group = request.match_info["uid"]
    new_values_for_user_in_group = await request.json()
    try:
        return await groups_api.update_user_in_group(
            request.app,
            user_id,
            gid,
            the_user_id_in_group,
            new_values_for_user_in_group,
        )
    except GroupNotFoundError:
        raise web.HTTPNotFound(reason=f"Group {gid} not found")
    except UserInGroupNotFoundError:
        raise web.HTTPNotFound(reason=f"User {the_user_id_in_group} not found")
    except UserInsufficientRightsError:
        raise web.HTTPForbidden()


@login_required
@permission_required("groups.*")
async def delete_group_user(request: web.Request):
    user_id = request[RQT_USERID_KEY]
    gid = request.match_info["gid"]
    the_user_id_in_group = request.match_info["uid"]
    try:
        await groups_api.delete_user_in_group(
            request.app, user_id, gid, the_user_id_in_group
        )
        raise web.HTTPNoContent()
    except GroupNotFoundError:
        raise web.HTTPNotFound(reason=f"Group {gid} not found")
    except UserInGroupNotFoundError:
        raise web.HTTPNotFound(reason=f"User {the_user_id_in_group} not found")
    except UserInsufficientRightsError:
        raise web.HTTPForbidden()
