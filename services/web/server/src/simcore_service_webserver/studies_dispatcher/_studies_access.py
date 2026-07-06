"""handles access to *public* studies

Handles a request to share a given sharable study via '/study/{id}'

- defines '/study/{id}' routes (this route does NOT belong to restAPI)
- access to projects management subsystem
- access to statics
- access to security
- access to login
"""

import functools
import logging
from functools import lru_cache
from uuid import UUID, uuid5

from aiohttp import web
from aiohttp_session import get_session
from common_library.error_codes import create_error_code
from common_library.logging.logging_errors import create_troubleshooting_log_kwargs
from models_library.projects import ProjectID
from servicelib.aiohttp import status
from servicelib.aiohttp.typing_extension import Handler

from ..constants import INDEX_RESOURCE_NAME
from ..products import products_web
from ..projects._groups_repository import get_project_group
from ..projects._projects_repository_legacy import ProjectDBAPI
from ..projects.exceptions import (
    ProjectGroupNotFoundError,
    ProjectInvalidRightsError,
    ProjectNotFoundError,
)
from ..projects.models import ProjectDict
from ..security import security_web
from ..utils import compose_support_error_msg
from ..utils_aiohttp import create_redirect_to_page_response
from ._constants import (
    MSG_LOGIN_REQUIRED,
    MSG_PROJECT_NOT_FOUND,
    MSG_PROJECT_NOT_PUBLISHED,
    MSG_PUBLIC_PROJECT_NOT_PUBLISHED,
    MSG_TOO_MANY_GUESTS,
    MSG_UNEXPECTED_DISPATCH_ERROR,
)
from ._errors import GuestUsersLimitError
from ._guards import check_studies_dispatcher_enabled
from ._users import create_temporary_guest_user, get_authorized_user
from .settings import get_plugin_settings

_logger = logging.getLogger(__name__)

_BASE_UUID = UUID("71e0eb5e-0797-4469-89ba-00a0df4d338a")


@lru_cache
def _compose_uuid(template_uuid, user_id, query="") -> str:
    """Creates a new uuid composing a project's and user ids such that
    any template pre-assigned to a user

    Enforces a constraint: a user CANNOT have multiple copies of the same template
    """
    return str(uuid5(_BASE_UUID, str(template_uuid) + str(user_id) + str(query)))


async def _get_published_template_project(
    request: web.Request,
    project_uuid: str,
    *,
    is_user_authenticated: bool,
) -> ProjectDict:
    """
    Validates and returns a published template project if accessible.

    A project is accessible if:
    1. It exists and is a template
    2. It's published (if user is unauthenticated)
    3. It's shared with either EVERYONE group (gid=1) or the product's group with read access

    Raises:
        RedirectToFrontEndPageError: If project doesn't meet access requirements
    """
    db = ProjectDBAPI.get_from_app_context(request.app)
    product = products_web.get_current_product(request)
    only_public_projects = not is_user_authenticated

    # Helper to create appropriate error for current context
    def _create_access_denied_error(reason: str) -> RedirectToFrontEndPageError:
        _logger.debug(
            "Access denied to project %s (only_public=%s): %s",
            project_uuid,
            only_public_projects,
            reason,
        )

        if only_public_projects:
            return RedirectToFrontEndPageError(
                MSG_PUBLIC_PROJECT_NOT_PUBLISHED.format(support_email=product.support_email),
                error_code="PUBLIC_PROJECT_NOT_PUBLISHED",
                status_code=status.HTTP_401_UNAUTHORIZED,
            )

        return RedirectToFrontEndPageError(
            MSG_PROJECT_NOT_PUBLISHED.format(project_id=project_uuid),
            error_code="PROJECT_NOT_PUBLISHED",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    # Step 1: Verify project exists and meets template/published requirements
    try:
        prj, _ = await db.get_project_dict_and_type(
            project_uuid=project_uuid,
            only_templates=True,
            only_published=only_public_projects,
        )
    except (ProjectNotFoundError, ProjectInvalidRightsError) as err:
        raise _create_access_denied_error(err.debug_message()) from err

    # Step 2: Verify project is shared with appropriate groups
    groups_to_check = [1]  # group 1 = everyone
    if product.group_id is not None:
        groups_to_check.append(product.group_id)

    for gid in groups_to_check:
        try:
            project_group = await get_project_group(request.app, project_id=ProjectID(project_uuid), group_id=gid)
            if project_group.read:
                _logger.debug(
                    "Project %s accessible via group %s for product %s",
                    project_uuid,
                    gid,
                    product.name,
                )
                return prj
        except ProjectGroupNotFoundError:
            # This group doesn't have access, try next group
            continue

    # No group has read access
    reason = f"Project not shared with required groups {groups_to_check}"
    raise _create_access_denied_error(reason)


# HANDLERS --------------------------------------------------------


class RedirectToFrontEndPageError(Exception):
    def __init__(self, human_readable_message: str, error_code: str, status_code: int) -> None:
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
                status_code=status.HTTP_404_NOT_FOUND,
            ) from err

        except RedirectToFrontEndPageError as err:
            raise create_redirect_to_page_response(
                request.app,
                page="error",
                message=err.human_readable_message,
                status_code=err.status_code,
            ) from err

        except web.HTTPError as err:
            raise create_redirect_to_page_response(
                request.app,
                page="error",
                message=err.reason or MSG_UNEXPECTED_DISPATCH_ERROR,
                status_code=err.status_code,
            ) from err

        except Exception as err:
            error_code = create_error_code(err)
            user_error_msg = compose_support_error_msg(
                msg=MSG_UNEXPECTED_DISPATCH_ERROR,
                error_code=error_code,
            )
            _logger.exception(
                **create_troubleshooting_log_kwargs(
                    user_error_msg,
                    error=err,
                    error_code=error_code,
                    tip="Unexpected failure while dispatching study",
                )
            )

            raise create_redirect_to_page_response(
                request.app,
                page="error",
                message=user_error_msg,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
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
    # Check if studies dispatcher is enabled for this product
    check_studies_dispatcher_enabled(request)

    project_id = request.match_info["id"]
    assert request.app.router[INDEX_RESOURCE_NAME]  # nosec

    # Checks USER
    user = None
    is_anonymous_user = await security_web.is_anonymous(request)
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
            status_code=status.HTTP_404_NOT_FOUND,
        ) from exc

    # Get published PROJECT referenced in link
    template_project = await _get_published_template_project(
        request,
        project_id,
        is_user_authenticated=bool(user),
    )

    # Get or create a valid USER
    if not user:
        if get_plugin_settings(request.app).is_login_required():
            raise RedirectToFrontEndPageError(
                MSG_LOGIN_REQUIRED,
                error_code="LOGIN_REQUIRED",
                status_code=status.HTTP_401_UNAUTHORIZED,
            )

        try:
            _logger.debug("Creating temporary user ... [%s]", f"{is_anonymous_user=}")
            user = await create_temporary_guest_user(request)
            is_anonymous_user = True

        except GuestUsersLimitError as exc:
            #
            # NOTE: Creation of guest users is limited. For that
            # reason we respond with 429 and inform the user that temporarily
            # we cannot accept any more users.
            #
            error_code = create_error_code(exc)

            user_error_msg = MSG_TOO_MANY_GUESTS
            _logger.exception(
                **create_troubleshooting_log_kwargs(
                    user_error_msg,
                    error=exc,
                    error_code=error_code,
                    tip="Failed to create guest user. Responded with 429 Too Many Requests",
                )
            )

            raise RedirectToFrontEndPageError(
                user_error_msg,
                error_code=error_code,
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            ) from exc

    # Redirect immediately to the SPA dispatching route — the actual clone is done
    # by a separate POST /{VTAG}/studies/{id}:dispatch call from the SPA, which runs
    # as a long-running task so the user gets live progress feedback.
    assert user  # nosec

    # Creating REDIRECTION LINK — points to the SPA dispatch fragment, not the final study
    redirect_url = (
        request.app.router[INDEX_RESOURCE_NAME]
        .url_for()
        .with_fragment(f"/dispatch?study_id={template_project['uuid']}")
    )

    response = web.HTTPFound(location=redirect_url)
    if is_anonymous_user:
        _logger.debug("Auto login for anonymous user %s", user["name"])

        await security_web.remember_identity(
            request,
            response,
            user_email=user["email"],
        )

        # NOTE: session is encrypted and stored in a cookie in the session middleware
        assert (await get_session(request))["AIOHTTP_SECURITY"] is not None  # nosec

    # WARNING: do NOT raise this response. From aiohttp 3.7.X, response is rebuild and cookie ignore.
    return response
