# pylint: disable=no-value-for-parameter

import json
import logging
from typing import List, Optional

from aiohttp import web

from . import groups_api
from .groups_classifiers import GroupClassifierRepository, build_rrids_tree_view
from .groups_exceptions import (
    GroupNotFoundError,
    UserInGroupNotFoundError,
    UserInsufficientRightsError,
)
from .login.decorators import RQT_USERID_KEY, login_required
from .scicrunch.scicrunch_db import ResearchResourceRepository
from .scicrunch.scicrunch_models import ResearchResource, ResourceHit
from .scicrunch.service_client import InvalidRRID, SciCrunch, ScicrunchError
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
    except GroupNotFoundError as exc:
        raise web.HTTPNotFound(reason=f"Group {gid} not found") from exc


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
    except UserNotFoundError as exc:
        raise web.HTTPNotFound(reason=f"User {user_id} not found") from exc


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
    except GroupNotFoundError as exc:
        raise web.HTTPNotFound(reason=f"Group {gid} not found") from exc
    except UserInsufficientRightsError as exc:
        raise web.HTTPForbidden() from exc


@login_required
@permission_required("groups.*")
async def delete_group(request: web.Request):
    user_id = request[RQT_USERID_KEY]
    gid = request.match_info["gid"]
    try:
        await groups_api.delete_user_group(request.app, user_id, gid)
        raise web.HTTPNoContent()
    except GroupNotFoundError as exc:
        raise web.HTTPNotFound(reason=f"Group {gid} not found") from exc
    except UserInsufficientRightsError as exc:
        raise web.HTTPForbidden() from exc


# groups/{gid}/users --------------------------------------------
@login_required
@permission_required("groups.*")
async def get_group_users(request: web.Request):
    user_id = request[RQT_USERID_KEY]
    gid = request.match_info["gid"]
    try:
        return await groups_api.list_users_in_group(request.app, user_id, gid)
    except GroupNotFoundError as exc:
        raise web.HTTPNotFound(reason=f"Group {gid} not found") from exc
    except UserInsufficientRightsError as exc:
        raise web.HTTPForbidden() from exc


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
    except GroupNotFoundError as exc:
        raise web.HTTPNotFound(reason=f"Group {gid} not found") from exc
    except UserInGroupNotFoundError as exc:
        raise web.HTTPNotFound(reason=f"User not found in group {gid}") from exc
    except UserInsufficientRightsError as exc:
        raise web.HTTPForbidden() from exc


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
    except GroupNotFoundError as exc:
        raise web.HTTPNotFound(reason=f"Group {gid} not found") from exc
    except UserInGroupNotFoundError as exc:
        raise web.HTTPNotFound(reason=f"User {the_user_id_in_group} not found") from exc
    except UserInsufficientRightsError as exc:
        raise web.HTTPForbidden() from exc


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
    except GroupNotFoundError as exc:
        raise web.HTTPNotFound(reason=f"Group {gid} not found") from exc
    except UserInGroupNotFoundError as exc:
        raise web.HTTPNotFound(reason=f"User {the_user_id_in_group} not found") from exc
    except UserInsufficientRightsError as exc:
        raise web.HTTPForbidden() from exc


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
    except GroupNotFoundError as exc:
        raise web.HTTPNotFound(reason=f"Group {gid} not found") from exc
    except UserInGroupNotFoundError as exc:
        raise web.HTTPNotFound(reason=f"User {the_user_id_in_group} not found") from exc
    except UserInsufficientRightsError as exc:
        raise web.HTTPForbidden() from exc


# GET groups/{gid}/classifiers --------------------------------------------
@login_required
@permission_required("groups.*")
async def get_group_classifiers(request: web.Request):
    try:
        gid = int(request.match_info["gid"])
        # FIXME: Raise ValidationError and handle as bad request.
        # Now middleware will convert as server error but it is a client error

        repo = GroupClassifierRepository(request.app)
        if not await repo.group_uses_scicrunch(gid):
            return await repo.get_classifiers_from_bundle(gid)

        # otherwise, build dynamic tree with RRIDs
        return await build_rrids_tree_view(
            request.app, tree_view_mode=request.query.get("tree_view", "std")
        )
    except ScicrunchError:
        return {}


#  GET /groups/sparc/classifiers/scicrunch-resources/{rrid}
@login_required
@permission_required("groups.*")
async def get_scicrunch_resource(request: web.Request):
    try:
        rrid = request.match_info["rrid"]
        rrid = SciCrunch.validate_identifier(rrid)

        # check if in database first
        repo = ResearchResourceRepository(request.app)
        resource: Optional[ResearchResource] = await repo.get_resource(rrid)
        if not resource:
            # otherwise, request to scicrunch service
            scicrunch = SciCrunch.get_instance(request.app)
            resource = await scicrunch.get_resource_fields(rrid)

        return resource.dict()

    except InvalidRRID as err:
        raise web.HTTPBadRequest(reason=err.reason) from err

    except ScicrunchError as err:
        user_msg = "Cannot get RRID since scicrunch.org service is not reachable."
        logger.error("%s -> %s", err, user_msg)
        raise web.HTTPServiceUnavailable(reason=user_msg) from err


#  POST /groups/sparc/classifiers/scicrunch-resources/{rrid}
@login_required
@permission_required("groups.*")
async def add_scicrunch_resource(request: web.Request):
    try:
        rrid = request.match_info["rrid"]

        # check if exists
        repo = ResearchResourceRepository(request.app)
        resource: Optional[ResearchResource] = await repo.get_resource(rrid)
        if not resource:
            # then request scicrunch service
            scicrunch = SciCrunch.get_instance(request.app)
            resource = await scicrunch.get_resource_fields(rrid)

            # insert new or if exists, then update
            await repo.upsert(resource)

        return resource.dict()

    except InvalidRRID as err:
        raise web.HTTPBadRequest(reason=err.reason) from err

    except ScicrunchError as err:
        user_msg = "Cannot add RRID since scicrunch.org service is not reachable."
        logger.error("%s -> %s", err, user_msg)
        raise web.HTTPServiceUnavailable(reason=user_msg) from err


#  GET /groups/sparc/classifiers/scicrunch-resources:search
@login_required
@permission_required("groups.*")
async def search_scicrunch_resources(request: web.Request):
    try:
        guess_name = str(request.query["guess_name"]).strip()

        scicrunch = SciCrunch.get_instance(request.app)
        hits: List[ResourceHit] = await scicrunch.search_resource(guess_name)

        return [hit.dict() for hit in hits]

    except ScicrunchError as err:
        user_msg = "Cannot search since scicrunch.org service is not reachable."
        logger.error("%s -> %s", err, user_msg)
        raise web.HTTPServiceUnavailable(reason=user_msg) from err
