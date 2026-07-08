"""Long-running task for dispatching (cloning) a published study into a user's account.

This module implements the TaskProtocol callable ``dispatch_study`` and the
registration helper ``register_dispatch_study_task``.

Flow:
    1. ``GET /study/{id}`` validates access, creates the guest session and redirects
       immediately to the SPA dispatching fragment (see ``_studies_access.py``).
    2. The SPA calls ``POST /{API_VTAG}/studies/{study_id}:dispatch``.
    3. That controller validates accessibility **synchronously** (pre-flight), then calls
       ``start_long_running_task``.  A 4xx is returned immediately for inaccessible studies.
    4. This module runs the actual clone asynchronously and reports progress.
       Access is trusted from the controller; no redundant re-check here.
"""

import logging
from functools import lru_cache
from uuid import UUID, uuid5

from aiohttp import web
from common_library.json_serialization import json_dumps
from models_library.projects import ProjectID
from servicelib.long_running_tasks.models import TaskProgress
from servicelib.long_running_tasks.task import TaskRegistry
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from servicelib.redis import RedisClientSDK, exclusive

from ..garbage_collector.garbage_collector_service import GUEST_USER_RC_LOCK_FORMAT
from ..projects.api import (
    clone_project_data,
    copy_allow_guests_to_push_states_and_output_ports,
    get_project_dict_and_type,
)
from ..projects.exceptions import ProjectNotFoundError
from ..redis import get_redis_lock_manager_client_sdk
from ..users.users_service import get_user

_logger = logging.getLogger(__name__)

_BASE_UUID = UUID("71e0eb5e-0797-4469-89ba-00a0df4d338a")


@lru_cache
def _compose_uuid(
    template_uuid: ProjectID | str,
    user_id: int,
    query: str | tuple[tuple[str, str], ...] = "",
) -> str:
    """Creates a deterministic UUID for a (template, user, query) tuple.

    Enforces a constraint: a user cannot have multiple copies of the same template.
    """
    return str(uuid5(_BASE_UUID, f"{template_uuid}{user_id}{query}"))


def _lock_redis_client(app: web.Application, *_args, **_kwargs) -> RedisClientSDK:
    return get_redis_lock_manager_client_sdk(app)


def _lock_key(_app: web.Application, user_name: str, *_args, **_kwargs) -> str:
    return GUEST_USER_RC_LOCK_FORMAT.format(user_id=user_name)


@exclusive(_lock_redis_client, lock_key=_lock_key)
async def _clone_study_with_gc_lock(
    app: web.Application,
    user_name: str,  # noqa: ARG001  # used by @exclusive for lock key  # pylint: disable=unused-argument
    *,
    progress: TaskProgress,
    template_project: dict,
    project_uuid: str,
    template_parameters: dict[str, str],
    user_id: int,
    product_name: str,
    product_api_base_url: str,
) -> None:
    """Performs the actual clone while holding the guest-user GC lock."""
    try:
        # Check if copy already exists (idempotent) — access already validated by the controller
        await get_project_dict_and_type(app, project_uuid)
        _logger.debug("Study copy %s already exists for user %s, skipping clone", project_uuid, user_id)

    except ProjectNotFoundError:
        # New project cloned from template
        await progress.update(message="cloning study document...", percent=0.05)

        new_project = await clone_project_data(
            app,
            source_project=template_project,
            forced_copy_project_id=ProjectID(project_uuid),
            user_id=user_id,
            product_name=product_name,
            product_api_base_url=product_api_base_url,
            task_progress=progress,
            template_parameters=template_parameters,
        )

        await copy_allow_guests_to_push_states_and_output_ports(
            app,
            from_project_uuid=template_project["uuid"],
            to_project_uuid=new_project["uuid"],
        )


async def dispatch_study(  # pylint: disable=too-many-arguments
    progress: TaskProgress,
    *,
    app: web.Application,
    study_id: str,
    user_id: int,
    product_name: str,
    template_parameters: dict[str, str],
    product_api_base_url: str,
) -> web.HTTPOk:
    """Implements TaskProtocol: clones a published study into the requesting user's account.

    Access has already been validated synchronously by the controller before enqueuing this task.

    Returns:
        200 response whose body contains ``{"project_id": "<uuid>"}``

    Raises:
        web.HTTPNotFound: if the study was deleted between controller check and task execution
    """
    await progress.update(message="loading study...")

    # Load the template project — access was already validated by the controller
    try:
        template_project, _ = await get_project_dict_and_type(
            app,
            study_id,
            only_templates=True,
        )
    except ProjectNotFoundError as exc:
        raise web.HTTPNotFound(reason=f"Study {study_id} not found") from exc

    await progress.update(message="preparing clone...", percent=0.03)

    # Look up user record for the GC lock key (needs user["name"])
    user = await get_user(app, user_id)

    # Deterministic copy UUID — idempotent re-dispatch for the same (template, user) pair
    project_uuid = _compose_uuid(template_project["uuid"], user_id, str(template_parameters))

    await _clone_study_with_gc_lock(
        app,
        user["name"],
        progress=progress,
        template_project=template_project,
        project_uuid=project_uuid,
        template_parameters=template_parameters,
        user_id=user_id,
        product_name=product_name,
        product_api_base_url=product_api_base_url,
    )

    await progress.update(message="done", percent=1.0)

    return web.HTTPOk(
        text=json_dumps({"data": {"project_id": project_uuid}}),
        content_type=MIMETYPE_APPLICATION_JSON,
    )


def register_dispatch_study_task(app: web.Application) -> None:
    TaskRegistry.register(
        dispatch_study,
        allowed_errors=(
            web.HTTPNotFound,
            web.HTTPForbidden,
            web.HTTPBadRequest,
        ),
        app=app,
    )
