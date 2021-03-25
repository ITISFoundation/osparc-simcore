""" handles access to *public* studies

    Handles a request to share a given sharable study via '/study/{id}'

    - defines '/study/{id}' routes (this route does NOT belong to restAPI)
    - access to projects management subsystem
    - access to statics
    - access to security
    - access to login

FIXME: Refactor to reduce modules coupling! See all TODO: .``from ...`` comments
"""
import logging
import uuid
from functools import lru_cache
from typing import Dict

from aiohttp import web
from aioredlock import Aioredlock
from servicelib.application_keys import APP_CONFIG_KEY
from servicelib.application_setup import ModuleCategory, app_module_setup

from .login.decorators import login_required
from .resource_manager.config import (
    APP_CLIENT_REDIS_LOCK_KEY,
    GUEST_USER_RC_LOCK_FORMAT,
)
from .security_api import is_anonymous, remember
from .statics import INDEX_RESOURCE_NAME
from .storage_api import copy_data_folders_from_project
from .utils import compose_error_msg

log = logging.getLogger(__name__)

BASE_UUID = uuid.UUID("71e0eb5e-0797-4469-89ba-00a0df4d338a")


@lru_cache()
def compose_uuid(template_uuid, user_id, query="") -> str:
    """Creates a new uuid composing a project's and user ids such that
    any template pre-assigned to a user

    Enforces a constraint: a user CANNOT have multiple copies of the same template
    """
    new_uuid = str(
        uuid.uuid5(BASE_UUID, str(template_uuid) + str(user_id) + str(query))
    )
    return new_uuid


# TODO: from .projects import get_public_project
async def get_public_project(app: web.Application, project_uuid: str):
    """
    Returns project if project_uuid is a template and is marked as published, otherwise None
    """
    from .projects.projects_db import APP_PROJECT_DBAPI

    db = app[APP_PROJECT_DBAPI]
    prj = await db.get_template_project(project_uuid, only_published=True)
    return prj


async def create_temporary_user(request: web.Request):
    """
    TODO: user should have an expiration date and limited persmissions!
    """
    from .login.cfg import get_storage
    from .login.handlers import ACTIVE, GUEST
    from .login.utils import get_client_ip, get_random_string
    from .security_api import encrypt_password

    db = get_storage(request.app)
    lock_manager: Aioredlock = request.app[APP_CLIENT_REDIS_LOCK_KEY]

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
    #
    MAX_DELAY_TO_CREATE_USER = 3  # secs
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
    async with await lock_manager.lock(
        GUEST_USER_RC_LOCK_FORMAT.format(user_id=random_uname),
        lock_timeout=MAX_DELAY_TO_CREATE_USER,
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
        await lock_manager.lock(
            GUEST_USER_RC_LOCK_FORMAT.format(user_id=user["id"]),
            lock_timeout=MAX_DELAY_TO_GUEST_FIRST_CONNECTION,
        )

    return user


# TODO: from .users import get_user?
async def get_authorized_user(request: web.Request) -> Dict:
    from .login.cfg import get_storage
    from .security_api import authorized_userid

    db = get_storage(request.app)
    userid = await authorized_userid(request)
    user = await db.get_user({"id": userid})
    return user


# TODO: from .projects import ...?
async def copy_study_to_account(
    request: web.Request, template_project: Dict, user: Dict
):
    """
    Creates a copy of the study to a given project in user's account

    - Replaces template parameters by values passed in query
    - Avoids multiple copies of the same template on each account
    """
    from .projects.projects_db import APP_PROJECT_DBAPI
    from .projects.projects_exceptions import ProjectNotFoundError
    from .projects.projects_utils import (
        clone_project_document,
        substitute_parameterized_inputs,
    )

    # FIXME: ONLY projects should have access to db since it avoids access layer
    # TODO: move to project_api and add access layer
    db = request.config_dict[APP_PROJECT_DBAPI]
    template_parameters = dict(request.query)

    # assign id to copy
    project_uuid = compose_uuid(
        template_project["uuid"], user["id"], str(template_parameters)
    )

    try:
        # Avoids multiple copies of the same template on each account
        await db.get_user_project(user["id"], project_uuid)

        # FIXME: if template is parametrized and user has already a copy, then delete it and create a new one??

    except ProjectNotFoundError:
        # New project cloned from template
        project, nodes_map = clone_project_document(
            template_project, forced_copy_project_id=project_uuid
        )

        # remove template access rights
        # FIXME: temporary fix until. Unify access management while cloning a project. Right not, at least two workflows have different implementations
        project["accessRights"] = {}

        # check project inputs and substitute template_parameters
        if template_parameters:
            log.info("Substituting parameters '%s' in template", template_parameters)
            project = (
                substitute_parameterized_inputs(project, template_parameters) or project
            )

        # add project model + copy data TODO: guarantee order and atomicity
        await db.add_project(project, user["id"], force_project_uuid=True)
        await copy_data_folders_from_project(
            request.app,
            template_project,
            project,
            nodes_map,
            user["id"],
        )

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

    template_project = await get_public_project(request.app, project_id)
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

    if not user:
        log.debug("Creating temporary user ...")
        user = await create_temporary_user(request)
        is_anonymous_user = True

    try:
        log.debug(
            "Granted access to study '%s' for user %s. Copying study over ...",
            template_project.get("name"),
            user.get("email"),
        )
        copied_project_id = await copy_study_to_account(request, template_project, user)

        log.debug("Study %s copied", copied_project_id)

    except Exception as exc:  # pylint: disable=broad-except
        log.exception(
            "Failed while copying project '%s' to '%s'",
            template_project.get("name"),
            user.get("email"),
        )
        raise web.HTTPInternalServerError(
            reason=compose_error_msg("Unable to copy project.")
        ) from exc

    try:
        redirect_url = (
            request.app.router[INDEX_RESOURCE_NAME]
            .url_for()
            .with_fragment("/study/{}".format(copied_project_id))
        )
    except KeyError as exc:
        log.exception(
            "Cannot redirect to website because route was not registered. Probably qx output was not ready and it was disabled (see statics.py)"
        )
        raise web.HTTPInternalServerError(
            reason=compose_error_msg("Unable to serve front-end.")
        ) from exc

    response = web.HTTPFound(location=redirect_url)
    if is_anonymous_user:
        log.debug("Auto login for anonymous user %s", user["name"])
        identity = user["email"]
        await remember(request, response, identity)

    raise response


@app_module_setup(__name__, ModuleCategory.ADDON, logger=log)
def setup(app: web.Application):

    cfg = app[APP_CONFIG_KEY]["main"]
    # TODO: temporarily used to toggle to logged users
    study_handler = get_redirection_to_study_page
    if not cfg["studies_access_enabled"]:
        study_handler = login_required(get_redirection_to_study_page)
        log.warning(
            "'%s' config explicitly disables anonymous users from this feature",
            __name__,
        )

    # TODO: make sure that these routes are filtered properly in active middlewares
    app.router.add_routes(
        [
            web.get(r"/study/{id}", study_handler, name="study"),
        ]
    )

    return True


# alias
setup_studies_access = setup

__all__ = "setup_studies_access"
