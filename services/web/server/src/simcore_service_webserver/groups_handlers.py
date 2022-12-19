import functools
import json
import logging
from typing import Optional

from aiohttp import web
from servicelib.aiohttp.typing_extension import Handler
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON

from . import groups_api
from ._meta import API_VTAG
from .groups_classifiers import GroupClassifierRepository, build_rrids_tree_view
from .groups_exceptions import (
    GroupNotFoundError,
    UserInGroupNotFoundError,
    UserInsufficientRightsError,
)
from .login.decorators import RQT_USERID_KEY, login_required
from .scicrunch.db import ResearchResourceRepository
from .scicrunch.errors import ScicrunchError
from .scicrunch.models import ResearchResource, ResourceHit
from .scicrunch.service_client import InvalidRRID, SciCrunch
from .security_decorators import permission_required
from .users_exceptions import UserNotFoundError

logger = logging.getLogger(__name__)


def _handle_groups_exceptions(handler: Handler):
    @functools.wraps(handler)
    async def wrapper(request: web.Request) -> web.Response:
        try:
            return await handler(request)

        except UserNotFoundError as exc:
            raise web.HTTPNotFound(reason=f"User {exc.uid} not found") from exc

        except GroupNotFoundError as exc:
            raise web.HTTPNotFound(reason=f"Group {exc.gid} not found") from exc

        except UserInGroupNotFoundError as exc:
            raise web.HTTPNotFound(reason=f"User not found in group {exc.gid}") from exc

        except UserInsufficientRightsError as exc:
            raise web.HTTPForbidden() from exc

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
    user_id = request[RQT_USERID_KEY]
    primary_group, user_groups, all_group = await groups_api.list_user_groups(
        request.app, user_id
    )

    # TODO: filter product

    return {
        "me": primary_group,
        "organizations": user_groups,  # read/write
        ## TODO: "product_all": product_group,
        "all": all_group,
    }


@routes.get(f"/{API_VTAG}/groups/{{gid}}", name="get_group")
@login_required
@permission_required("groups.read")
@_handle_groups_exceptions
async def get_group(request: web.Request):
    """Get one group details"""
    user_id = request[RQT_USERID_KEY]
    gid = request.match_info["gid"]

    return await groups_api.get_user_group(request.app, user_id, gid)


@routes.post(f"/{API_VTAG}/groups", name="create_group")
@login_required
@permission_required("groups.*")
@_handle_groups_exceptions
async def create_group(request: web.Request):
    """Creates organization groups"""
    user_id = request[RQT_USERID_KEY]
    new_group = await request.json()

    created_group = await groups_api.create_user_group(request.app, user_id, new_group)
    raise web.HTTPCreated(
        text=json.dumps({"data": created_group}), content_type=MIMETYPE_APPLICATION_JSON
    )


@routes.patch(f"/{API_VTAG}/groups/{{gid}}", name="update_group")
@login_required
@permission_required("groups.*")
@_handle_groups_exceptions
async def update_group(request: web.Request):
    user_id = request[RQT_USERID_KEY]
    gid = request.match_info["gid"]
    new_group_values = await request.json()

    return await groups_api.update_user_group(
        request.app, user_id, gid, new_group_values
    )


@routes.delete(f"/{API_VTAG}/groups/{{gid}}", name="update_group")
@login_required
@permission_required("groups.*")
@_handle_groups_exceptions
async def delete_group(request: web.Request):
    user_id = request[RQT_USERID_KEY]
    gid = request.match_info["gid"]

    await groups_api.delete_user_group(request.app, user_id, gid)
    raise web.HTTPNoContent()


@routes.get(f"/{API_VTAG}/groups/{{gid}}/users", name="get_group_users")
@login_required
@permission_required("groups.*")
@_handle_groups_exceptions
async def get_group_users(request: web.Request):
    user_id = request[RQT_USERID_KEY]
    gid = request.match_info["gid"]

    return await groups_api.list_users_in_group(request.app, user_id, gid)


@routes.post(f"/{API_VTAG}/groups/{{gid}}/users", name="add_group_user")
@login_required
@permission_required("groups.*")
@_handle_groups_exceptions
async def add_group_user(request: web.Request):
    """
    Adds a user in an organization group
    """
    user_id = request[RQT_USERID_KEY]
    gid = request.match_info["gid"]
    new_user_in_group = await request.json()
    # TODO: validate!!
    assert "uid" in new_user_in_group or "email" in new_user_in_group  # nosec

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


@routes.get(f"/{API_VTAG}/groups/{{gid}}/users/{{uid}}", name="get_group_user")
@login_required
@permission_required("groups.*")
@_handle_groups_exceptions
async def get_group_user(request: web.Request):
    """
    Gets specific user in group
    """
    user_id = request[RQT_USERID_KEY]
    gid = request.match_info["gid"]
    the_user_id_in_group = request.match_info["uid"]
    return await groups_api.get_user_in_group(
        request.app, user_id, gid, the_user_id_in_group
    )


@routes.patch(f"/{API_VTAG}/groups/{{gid}}/users/{{uid}}", name="update_group_user")
@login_required
@permission_required("groups.*")
@_handle_groups_exceptions
async def update_group_user(request: web.Request):
    """
    Modify specific user in group
    """
    user_id = request[RQT_USERID_KEY]
    gid = request.match_info["gid"]
    the_user_id_in_group = request.match_info["uid"]
    new_values_for_user_in_group = await request.json()
    return await groups_api.update_user_in_group(
        request.app,
        user_id,
        gid,
        the_user_id_in_group,
        new_values_for_user_in_group,
    )


@routes.delete(f"/{API_VTAG}/groups/{{gid}}/users/{{uid}}", name="delete_group_user")
@login_required
@permission_required("groups.*")
@_handle_groups_exceptions
async def delete_group_user(request: web.Request):
    user_id = request[RQT_USERID_KEY]
    gid = request.match_info["gid"]
    the_user_id_in_group = request.match_info["uid"]
    await groups_api.delete_user_in_group(
        request.app, user_id, gid, the_user_id_in_group
    )
    raise web.HTTPNoContent()


@routes.get(f"/{API_VTAG}/groups/{{gid}}/classifiers", name="get_group_classifiers")
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


def _handle_scicrunch_exceptions(handler: Handler):
    @functools.wraps(handler)
    async def wrapper(request: web.Request) -> web.Response:
        try:
            return await handler(request)

        except InvalidRRID as err:
            raise web.HTTPBadRequest(reason=err.reason) from err

        except ScicrunchError as err:
            user_msg = "Cannot get RRID since scicrunch.org service is not reachable."
            logger.error("%s -> %s", err, user_msg)
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
    resource: Optional[ResearchResource] = await repo.get_resource(rrid)
    if not resource:
        # otherwise, request to scicrunch service
        scicrunch = SciCrunch.get_instance(request.app)
        resource = await scicrunch.get_resource_fields(rrid)

    return resource.dict()


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
    resource: Optional[ResearchResource] = await repo.get_resource(rrid)
    if not resource:
        # then request scicrunch service
        scicrunch = SciCrunch.get_instance(request.app)
        resource = await scicrunch.get_resource_fields(rrid)

        # insert new or if exists, then update
        await repo.upsert(resource)

    return resource.dict()


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

    return [hit.dict() for hit in hits]
