""" handles access to *public* studies

    Handles a request to share a given sharable study via '/study/{id}'

    - defines '/study/{id}' routes (this route does NOT belong to restAPI)
    - access to projects management subsystem
    - access to statics
    - access to security
    - access to login


NOTE: Some of the code below is duplicated in the studies_dispatcher!
SEE refactoring plan in https://github.com/ITISFoundation/osparc-simcore/issues/3977
"""
import functools
import logging
from datetime import datetime
from functools import lru_cache
from uuid import UUID, uuid5

import redis.asyncio as aioredis
from aiohttp import web
from aiohttp_session import get_session
from models_library.emails import LowerCaseEmailStr
from models_library.projects import ProjectID
from pydantic import parse_obj_as
from servicelib.aiohttp.typing_extension import Handler
from servicelib.error_codes import create_error_code

from .._constants import INDEX_RESOURCE_NAME
from ..director_v2._core_computations import create_or_update_pipeline
from ..garbage_collector.settings import GUEST_USER_RC_LOCK_FORMAT
from ..products.api import get_current_product, get_product_name
from ..projects.db import ANY_USER, ProjectDBAPI
from ..projects.exceptions import ProjectInvalidRightsError, ProjectNotFoundError
from ..projects.models import ProjectDict
from ..redis import get_redis_lock_manager_client
from ..security.api import is_anonymous, remember
from ..storage.api import copy_data_folders_from_project
from ..utils import compose_support_error_msg
from ..utils_aiohttp import create_redirect_to_page_response
from ._constants import (
    MSG_PROJECT_NOT_FOUND,
    MSG_PROJECT_NOT_PUBLISHED,
    MSG_PUBLIC_PROJECT_NOT_PUBLISHED,
    MSG_UNEXPECTED_ERROR,
)
from .settings import StudiesDispatcherSettings, get_plugin_settings

_logger = logging.getLogger(__name__)

_BASE_UUID = UUID("71e0eb5e-0797-4469-89ba-00a0df4d338a")


@lru_cache
def _compose_uuid(template_uuid, user_id, query="") -> str:
    """Creates a new uuid composing a project's and user ids such that
    any template pre-assigned to a user

    Enforces a constraint: a user CANNOT have multiple copies of the same template
    """
    new_uuid = str(uuid5(_BASE_UUID, str(template_uuid) + str(user_id) + str(query)))
    return new_uuid


async def _get_published_template_project(
    request: web.Request,
    project_uuid: str,
    *,
    is_user_authenticated: bool,
) -> ProjectDict:
    """
    raises RedirectToFrontEndPageError
    """
    db = ProjectDBAPI.get_from_app_context(request.app)

    only_public_projects = not is_user_authenticated

    try:
        prj, _ = await db.get_project(
            project_uuid=project_uuid,
            # NOTE: these are the conditions for a published study
            # 1. MUST be a template
            only_templates=True,
            # 2. If user is unauthenticated, then MUST be public
            only_published=only_public_projects,
            # 3. MUST be shared with EVERYONE=1 in read mode, i.e.
            user_id=ANY_USER,  # any user
            check_permissions="read",  # any user has read access
        )
        if not prj:
            # Not sure this happens but this condition was checked before so better be safe
            raise ProjectNotFoundError(project_uuid)

        return prj

    except (ProjectNotFoundError, ProjectInvalidRightsError) as err:
        _logger.debug(
            "Project with %s %s was not found. Reason: %s",
            f"{project_uuid=}",
            f"{only_public_projects=}",
            err.detailed_message(),
        )

        support_email = get_current_product(request).support_email
        if only_public_projects:
            raise RedirectToFrontEndPageError(
                MSG_PUBLIC_PROJECT_NOT_PUBLISHED.format(support_email=support_email),
                error_code="PUBLIC_PROJECT_NOT_PUBLISHED",
                status_code=web.HTTPUnauthorized.status_code,
            ) from err

        raise RedirectToFrontEndPageError(
            MSG_PROJECT_NOT_PUBLISHED.format(project_id=project_uuid),
            error_code="PROJECT_NOT_PUBLISHED",
            status_code=web.HTTPNotFound.status_code,
        ) from err


async def _create_temporary_user(request: web.Request):
    from ..login.storage import AsyncpgStorage, get_plugin_storage
    from ..login.utils import ACTIVE, GUEST, get_random_string
    from ..security.api import encrypt_password

    db: AsyncpgStorage = get_plugin_storage(request.app)
    redis_locks_client: aioredis.Redis = get_redis_lock_manager_client(request.app)
    settings: StudiesDispatcherSettings = get_plugin_settings(app=request.app)

    # Profile for temporary user
    random_uname = get_random_string(min_len=5)
    email = parse_obj_as(LowerCaseEmailStr, f"{random_uname}@guest-at-osparc.io")
    password = get_random_string(min_len=12)
    expires_at = datetime.utcnow() + settings.STUDIES_GUEST_ACCOUNT_LIFETIME

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
                "expires_at": expires_at,
            }
        )
        # (2) read details above
        await redis_locks_client.lock(
            GUEST_USER_RC_LOCK_FORMAT.format(user_id=user["id"]),
            timeout=MAX_DELAY_TO_GUEST_FIRST_CONNECTION,
        ).acquire()

    return user


async def get_authorized_user(request: web.Request) -> dict:
    from ..login.storage import AsyncpgStorage, get_plugin_storage
    from ..security.api import authorized_userid

    db: AsyncpgStorage = get_plugin_storage(request.app)
    userid = await authorized_userid(request)
    user: dict = await db.get_user({"id": userid})
    return user


async def copy_study_to_account(
    request: web.Request, template_project: dict, user: dict
):
    """
    Creates a copy of the study to a given project in user's account

    - Replaces template parameters by values passed in query
    - Avoids multiple copies of the same template on each account
    """
    from ..projects.db import APP_PROJECT_DBAPI
    from ..projects.utils import clone_project_document, substitute_parameterized_inputs

    db: ProjectDBAPI = request.config_dict[APP_PROJECT_DBAPI]
    template_parameters = dict(request.query)

    # assign new uuid to copy
    project_uuid = _compose_uuid(
        template_project["uuid"], user["id"], str(template_parameters)
    )

    try:
        # Avoids multiple copies of the same template on each account
        await db.get_project(user["id"], project_uuid)

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
            _logger.info(
                "Substituting parameters '%s' in template", template_parameters
            )
            project = (
                substitute_parameterized_inputs(project, template_parameters) or project
            )
        # add project model + copy data TODO: guarantee order and atomicity
        product_name = get_product_name(request)
        await db.insert_project(
            project,
            user["id"],
            product_name=product_name,
            force_project_uuid=True,
            project_nodes=None,
        )
        async for lr_task in copy_data_folders_from_project(
            request.app,
            template_project,
            project,
            nodes_map,
            user["id"],
        ):
            _logger.info(
                "copying %s into %s for %s: %s",
                f"{template_project['uuid']=}",
                f"{project['uuid']}",
                f"{user['id']}",
                f"{lr_task.progress=}",
            )
            if lr_task.done():
                await lr_task.result()
        await create_or_update_pipeline(
            request.app, user["id"], project["uuid"], product_name
        )

    return project_uuid


# HANDLERS --------------------------------------------------------


class RedirectToFrontEndPageError(Exception):
    def __init__(
        self, human_readable_message: str, error_code: str, status_code: int
    ) -> None:
        self.human_readable_message = human_readable_message
        self.error_code = error_code
        self.status_code = status_code
        super().__init__(human_readable_message)


def _handle_errors_with_error_page(handler: Handler):
    @functools.wraps(handler)
    async def wrapper(request: web.Request) -> web.StreamResponse:
        try:
            return await handler(request)

        except ProjectNotFoundError as err:
            raise create_redirect_to_page_response(
                request.app,
                page="error",
                message=compose_support_error_msg(
                    msg=MSG_PROJECT_NOT_FOUND.format(project_id=err.project_uuid),
                    error_code="PROJECT_NOT_FOUND",
                ),
                status_code=web.HTTPNotFound.status_code,
            ) from err

        except RedirectToFrontEndPageError as err:
            raise create_redirect_to_page_response(
                request.app,
                page="error",
                message=err.human_readable_message,
                status_code=err.status_code,
            ) from err

        except Exception as err:
            error_code = create_error_code(err)
            _logger.exception(
                "Unexpected failure while dispatching study [%s]",
                f"{error_code}",
                extra={"error_code": error_code},
            )
            raise create_redirect_to_page_response(
                request.app,
                page="error",
                message=compose_support_error_msg(
                    msg=MSG_UNEXPECTED_ERROR.format(hint=""), error_code=error_code
                ),
                status_code=500,
            ) from err

    return wrapper


@_handle_errors_with_error_page
async def get_redirection_to_study_page(request: web.Request) -> web.Response:
    """
    Handles requests to get and open a public study

    - public studies are templates that are marked as published in the database
    - if user is not registered, it creates a temporary guest account with limited resources and expiration
    - this handler is NOT part of the API and therefore does NOT respond with json
    """
    project_id = request.match_info["id"]
    assert request.app.router[INDEX_RESOURCE_NAME]  # nosec

    # Checks USER
    user = None
    is_anonymous_user = await is_anonymous(request)
    if not is_anonymous_user:
        # NOTE: covers valid cookie with unauthorized user (e.g. expired guest/banned)
        user = await get_authorized_user(request)

    # This was added so it fails right away if study doesn't exist.
    # Work-around to check if there is a PROJECT with project_id: check the type of the project.
    try:
        db = ProjectDBAPI.get_from_app_context(request.app)
        await db.get_project_type(project_uuid=ProjectID(project_id))
    except ProjectNotFoundError as exc:
        raise RedirectToFrontEndPageError(
            MSG_PROJECT_NOT_FOUND.format(project_id=project_id),
            error_code="PROJECT_NOT_FOUND",
            status_code=web.HTTPNotFound.status_code,
        ) from exc

    # Get published PROJECT referenced in link
    template_project = await _get_published_template_project(
        request,
        project_id,
        is_user_authenticated=bool(user),
    )

    # Get or create a valid USER
    if not user:
        _logger.debug("Creating temporary user ...")
        user = await _create_temporary_user(request)
        is_anonymous_user = True

    # COPY
    try:
        _logger.debug(
            "Granted access to study '%s' for user %s. Copying study over ...",
            template_project.get("name"),
            user.get("email"),
        )
        copied_project_id = await copy_study_to_account(request, template_project, user)

        _logger.debug("Study %s copied", copied_project_id)

    except Exception as exc:  # pylint: disable=broad-except
        error_code = create_error_code(exc)
        _logger.exception(
            "Failed while copying project '%s' to '%s' [%s]",
            template_project.get("name"),
            user.get("email"),
            f"{error_code}",
            extra={"error_code": error_code},
        )
        raise RedirectToFrontEndPageError(
            MSG_UNEXPECTED_ERROR.format(hint="while copying your study"),
            error_code=error_code,
            status_code=web.HTTPInternalServerError.status_code,
        ) from exc

    # Creating REDIRECTION LINK
    redirect_url = (
        request.app.router[INDEX_RESOURCE_NAME]
        .url_for()
        .with_fragment(f"/study/{copied_project_id}")
    )

    response = web.HTTPFound(location=redirect_url)
    if is_anonymous_user:
        _logger.debug("Auto login for anonymous user %s", user["name"])
        identity = user["email"]

        await remember(request, response, identity)

        # NOTE: session is encrypted and stored in a cookie in the session middleware
        assert (await get_session(request))["AIOHTTP_SECURITY"] == identity  # nosec

    # WARNING: do NOT raise this response. From aiohttp 3.7.X, response is rebuild and cookie ignore.
    return response
