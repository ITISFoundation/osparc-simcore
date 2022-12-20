""" handles access to *public* studies

    Handles a request to share a given sharable study via '/study/{id}'

    - defines '/study/{id}' routes (this route does NOT belong to restAPI)
    - access to projects management subsystem
    - access to statics
    - access to security
    - access to login

TODO: Refactor to reduce modules coupling! See all TODO: .``from ...`` comments
"""
import logging
from functools import lru_cache
from uuid import UUID, uuid5

import redis.asyncio as aioredis
from aiohttp import web
from aiohttp_session import get_session
from servicelib.error_codes import create_error_code

from .._constants import INDEX_RESOURCE_NAME
from ..garbage_collector_settings import GUEST_USER_RC_LOCK_FORMAT
from ..products import get_product_name
from ..projects.projects_db import ProjectDBAPI
from ..projects.projects_exceptions import ProjectNotFoundError
from ..redis import get_redis_lock_manager_client
from ..security_api import is_anonymous, remember
from ..storage_api import copy_data_folders_from_project
from ..utils import compose_support_error_msg

log = logging.getLogger(__name__)

# TODO: Integrate this in studies_dispatcher
BASE_UUID = UUID("71e0eb5e-0797-4469-89ba-00a0df4d338a")


@lru_cache
def compose_uuid(template_uuid, user_id, query="") -> str:
    """Creates a new uuid composing a project's and user ids such that
    any template pre-assigned to a user

    Enforces a constraint: a user CANNOT have multiple copies of the same template
    """
    new_uuid = str(uuid5(BASE_UUID, str(template_uuid) + str(user_id) + str(query)))
    return new_uuid


async def get_public_project(app: web.Application, project_uuid: str):
    """
    Returns project if project_uuid is a template and is marked as published, otherwise None
    """
    db = ProjectDBAPI.get_from_app_context(app)
    prj, _ = await db.get_project(
        -1, project_uuid, only_published=True, only_templates=True
    )
    return prj


async def create_temporary_user(request: web.Request):
    """
    TODO: user should have an expiration date and limited persmissions!
    """
    from ..login.storage import AsyncpgStorage, get_plugin_storage
    from ..login.utils import ACTIVE, GUEST, get_client_ip, get_random_string
    from ..security_api import encrypt_password

    db: AsyncpgStorage = get_plugin_storage(request.app)
    redis_locks_client: aioredis.Redis = get_redis_lock_manager_client(request.app)

    # TODO: avatar is an icon of the hero!
    random_uname = get_random_string(min_len=5)
    email = random_uname + "@guest-at-osparc.io"
    password = get_random_string(min_len=12)

    # GUEST_USER_RC_LOCK:
    #
    #   These locks prevents the GC from deleting a GUEST user in to stages of its lifefime:
    #
    #  1. During construction:
    #     - Prevents GC from deleting this GUEST user while it is being created
    #     - Since the user still does not have an ID assigned, the lock is named with his random_uname
    #     - the timeout here is the TTL of the lock in Redis. in case the webserver is overwhelmed and cannot create
    #       a user during that time or crashes, then redis will ensure the lock disappears and let the garbage collector do its work
    #
    MAX_DELAY_TO_CREATE_USER = 13  # secs
    #
    #  2. During initialization
    #     - Prevents the GC from deleting this GUEST user, with ID assigned, while it gets initialized and acquires it's first resource
    #     - Uses the ID assigned to name the lock
    #
    MAX_DELAY_TO_GUEST_FIRST_CONNECTION = 15  # secs
    #
    #
    # NOTES:
    #   - In case of failure or excessive delay the lock has a timeout that automatically unlocks it
    #     and the GC can clean up what remains
    #   - Notice that the ids to name the locks are unique, therefore the lock can be acquired w/o errors
    #   - These locks are very specific to resources and have timeout so the risk of blocking from GC is small
    #

    # (1) read details above
    async with redis_locks_client.lock(
        GUEST_USER_RC_LOCK_FORMAT.format(user_id=random_uname),
        timeout=MAX_DELAY_TO_CREATE_USER,
    ):
        user = await db.create_user(
            {
                "name": random_uname,
                "email": email,
                "password_hash": encrypt_password(password),
                "status": ACTIVE,
                "role": GUEST,
                "created_ip": get_client_ip(request),
            }
        )
        # (2) read details above
        await redis_locks_client.lock(
            GUEST_USER_RC_LOCK_FORMAT.format(user_id=user["id"]),
            timeout=MAX_DELAY_TO_GUEST_FIRST_CONNECTION,
        ).acquire()

    return user


# TODO: from .users import get_user?
async def get_authorized_user(request: web.Request) -> dict:
    from ..login.storage import AsyncpgStorage, get_plugin_storage
    from ..security_api import authorized_userid

    db: AsyncpgStorage = get_plugin_storage(request.app)
    userid = await authorized_userid(request)
    user = await db.get_user({"id": userid})
    return user


# TODO: from .projects import ...?
async def copy_study_to_account(
    request: web.Request, template_project: dict, user: dict
):
    """
    Creates a copy of the study to a given project in user's account

    - Replaces template parameters by values passed in query
    - Avoids multiple copies of the same template on each account
    """
    from ..projects.projects_db import APP_PROJECT_DBAPI
    from ..projects.projects_utils import (
        clone_project_document,
        substitute_parameterized_inputs,
    )

    # FIXME: ONLY projects should have access to db since it avoids access layer
    # TODO: move to project_api and add access layer
    db: ProjectDBAPI = request.config_dict[APP_PROJECT_DBAPI]
    template_parameters = dict(request.query)

    # assign id to copy
    project_uuid = compose_uuid(
        template_project["uuid"], user["id"], str(template_parameters)
    )

    try:
        # Avoids multiple copies of the same template on each account
        await db.get_project(user["id"], project_uuid)

        # FIXME: if template is parametrized and user has already a copy, then delete it and create a new one??

    except ProjectNotFoundError:
        # New project cloned from template
        project, nodes_map = clone_project_document(
            template_project, forced_copy_project_id=UUID(project_uuid)
        )

        # remove template access rights
        # TODO: PC: what should I do with this stuff? can we re-use the same entrypoint?
        # FIXME: temporary fix until. Unify access management while cloning a project. Right not, at least two workflows have different implementations
        project["accessRights"] = {}

        # check project inputs and substitute template_parameters
        if template_parameters:
            log.info("Substituting parameters '%s' in template", template_parameters)
            project = (
                substitute_parameterized_inputs(project, template_parameters) or project
            )
        # add project model + copy data TODO: guarantee order and atomicity
        await db.add_project(
            project,
            user["id"],
            product_name=get_product_name(request),
            force_project_uuid=True,
        )
        async for lr_task in copy_data_folders_from_project(
            request.app,
            template_project,
            project,
            nodes_map,
            user["id"],
        ):
            log.info(
                "copying %s into %s for %s: %s",
                f"{template_project['uuid']=}",
                f"{project['uuid']}",
                f"{user['id']}",
                f"{lr_task.progress=}",
            )
            if lr_task.done():
                await lr_task.result()

    return project_uuid


# HANDLERS --------------------------------------------------------
async def get_redirection_to_study_page(request: web.Request) -> web.Response:
    """
    Handles requests to get and open a public study

    - public studies are templates that are marked as published in the database
    - if user is not registered, it creates a temporary guest account with limited resources and expiration
    - this handler is NOT part of the API and therefore does NOT respond with json
    """
    # TODO: implement nice error-page.html
    project_id = request.match_info["id"]

    try:
        template_project = await get_public_project(request.app, project_id)
    except ProjectNotFoundError as exc:
        raise web.HTTPNotFound(
            reason=f"Requested study ({project_id}) has not been published.\
             Please contact the data curators for more information."
        ) from exc
    if not template_project:
        raise web.HTTPNotFound(
            reason=f"Requested study ({project_id}) has not been published.\
             Please contact the data curators for more information."
        )

    # Get or create a valid user
    user = None
    is_anonymous_user = await is_anonymous(request)
    if not is_anonymous_user:
        # NOTE: covers valid cookie with unauthorized user (e.g. expired guest/banned)
        # TODO: test if temp user overrides old cookie properly
        user = await get_authorized_user(request)

    try:
        if not user:
            log.debug("Creating temporary user ...")
            user = await create_temporary_user(request)
            is_anonymous_user = True
    except Exception as exc:  # pylint: disable=broad-except
        error_code = create_error_code(exc)
        log.exception(
            "Failed while creating temporary user. TIP: too many simultaneous request? [%s]",
            f"{error_code}",
            extra={"error_code": error_code},
        )
        raise web.HTTPInternalServerError(
            reason=compose_support_error_msg(
                "Unable to create temporary user", error_code
            )
        ) from exc
    try:
        log.debug(
            "Granted access to study '%s' for user %s. Copying study over ...",
            template_project.get("name"),
            user.get("email"),
        )
        copied_project_id = await copy_study_to_account(request, template_project, user)

        log.debug("Study %s copied", copied_project_id)

    except Exception as exc:  # pylint: disable=broad-except
        error_code = create_error_code(exc)
        log.exception(
            "Failed while copying project '%s' to '%s' [%s]",
            template_project.get("name"),
            user.get("email"),
            f"{error_code}",
            extra={"error_code": error_code},
        )
        raise web.HTTPInternalServerError(
            reason=compose_support_error_msg("Unable to copy project", error_code)
        ) from exc

    try:
        redirect_url = (
            request.app.router[INDEX_RESOURCE_NAME]
            .url_for()
            .with_fragment(f"/study/{copied_project_id}")
        )
    except KeyError as exc:
        error_code = create_error_code(exc)
        log.exception(
            "Cannot redirect to website because route was not registered. "
            "Probably the static-webserver is disabled (see statics.py) [%s]",
            f"{error_code}",
            extra={"error_code": error_code},
        )
        raise web.HTTPInternalServerError(
            reason=compose_support_error_msg("Unable to serve front-end", error_code)
        ) from exc

    response = web.HTTPFound(location=redirect_url)
    if is_anonymous_user:
        log.debug("Auto login for anonymous user %s", user["name"])
        identity = user["email"]

        await remember(request, response, identity)

        assert (await get_session(request))["AIOHTTP_SECURITY"] == identity  # nosec

        # NOTE: session is encrypted and stored in a cookie in the session middleware

    # WARNING: do NOT raise this response. From aiohttp 3.7.X, response is rebuild and cookie ignore.
    # TODO: PC: security with SessionIdentityPolicy, session with EncryptedCookieStorage -> remember() and raise response.
    return response
