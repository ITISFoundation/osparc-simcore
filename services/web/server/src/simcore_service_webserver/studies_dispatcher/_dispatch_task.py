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

import asyncio
import logging
from functools import lru_cache
from typing import Annotated, Final
from uuid import UUID, uuid5

from aiohttp import web
from annotated_types import doc
from common_library.json_serialization import json_dumps
from models_library.projects import ProjectID
from models_library.users import UserID
from servicelib.logging_utils import log_catch
from servicelib.long_running_tasks.models import TaskProgress
from servicelib.long_running_tasks.task import TaskRegistry
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from servicelib.redis import RedisClientSDK, exclusive
from servicelib.utils import fire_and_forget_task

from ..constants import APP_FIRE_AND_FORGET_TASKS_KEY
from ..garbage_collector.garbage_collector_service import GUEST_USER_RC_LOCK_FORMAT
from ..projects import _projects_repository
from ..projects.api import (
    clone_project_data,
    copy_allow_guests_to_push_states_and_output_ports,
    get_project_dict_and_type,
)
from ..projects.exceptions import ProjectNotFoundError
from ..projects.projects_trash_service import delete_project_as_admin, trash_project_for_immediate_deletion
from ..redis import get_redis_lock_manager_client_sdk
from ..users.users_service import get_user

_logger = logging.getLogger(__name__)

_BASE_UUID = UUID("71e0eb5e-0797-4469-89ba-00a0df4d338a")

_COPY_CLEANUP_TIMEOUT_S: Final[
    Annotated[
        int,
        doc(
            "time budget of the best-effort deletion of a copy whose clone failed; the copy is "
            "stamped for the garbage-collector before it and the stamp survives a timeout"
        ),
    ]
] = 120


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


async def _safe_stamp_copy_for_immediate_deletion(
    app: web.Application, *, project_uuid: str, user_id: UserID, product_name: str
) -> None:
    with log_catch(_logger, reraise=False):
        await trash_project_for_immediate_deletion(
            app,
            product_name=product_name,
            user_id=user_id,
            project_id=ProjectID(project_uuid),
        )


async def _delete_copy_or_leave_it_to_gc(
    app: web.Application, *, project_uuid: str, user_id: UserID, product_name: str
) -> None:
    """Deletes a copy whose clone did not finish, or leaves it to the garbage-collector.

    The copy is stamped first — hidden and trashed in a single query: from then on it is
    invisible to dispatch and the garbage-collector deletes it even if this function does not
    complete; neither a timeout here nor a web-server shutdown interrupts that deletion. The
    direct delete below only frees the uuid sooner.

    A copy somebody already hid belongs to their deletion: it is only stamped here, never
    deleted, since two deleters of the same uuid can remove a clone recreated under it.
    """
    try:
        copy = await _projects_repository.get_project(app, project_uuid=ProjectID(project_uuid))
    except ProjectNotFoundError:
        return

    await _safe_stamp_copy_for_immediate_deletion(
        app, project_uuid=project_uuid, user_id=user_id, product_name=product_name
    )
    if copy.hidden:
        return

    try:
        async with asyncio.timeout(_COPY_CLEANUP_TIMEOUT_S):
            await delete_project_as_admin(app, project_uuid=ProjectID(project_uuid), product_name=product_name)
    except Exception, asyncio.CancelledError:  # pylint: disable=broad-exception-caught
        # stamped above: the garbage-collector retries the deletion on its next sweep
        _logger.warning("Left copy %s to the garbage-collector after its deletion did not complete", project_uuid)


async def _is_copy_finished(app: web.Application, *, project_uuid: str, user_id: UserID, product_name: str) -> bool:
    """Tells whether the copy exists and is a complete clone.

    A hidden copy is one whose deletion started and did not complete: the garbage-collector is
    deleting a copy a failed clone stamped, or somebody else is deleting the copy. Both are left
    to their deletion and the answer is 503: the uuid stays taken until the row is gone, and
    recreating the copy meanwhile would let those deleters remove the new clone by uuid. A hidden
    copy nobody stamped is stamped here, so the garbage-collector picks it up even if whoever hid
    it never returns.

    The copy is read once: `hidden` and `trashed` come from the same row, and the garbage-collector
    deletes the row as its last step, so a deletion in flight is always seen as a hidden row.

    Raises:
        web.HTTPServiceUnavailable: the copy is being deleted
    """
    try:
        copy = await _projects_repository.get_project(app, project_uuid=ProjectID(project_uuid))
    except ProjectNotFoundError:
        return False

    if copy.hidden:
        if copy.trashed is None:
            await _safe_stamp_copy_for_immediate_deletion(
                app, project_uuid=project_uuid, user_id=user_id, product_name=product_name
            )
        raise web.HTTPServiceUnavailable(reason="A previous clone of this study is being cleaned up, try again shortly")
    return True


@exclusive(_lock_redis_client, lock_key=_lock_key)
async def _clone_study_with_gc_lock(
    app: web.Application,
    user_name: str,  # noqa: ARG001  # used by @exclusive for lock key  # pylint: disable=unused-argument
    *,
    progress: TaskProgress,
    template_project: dict,
    project_uuid: str,
    template_parameters: dict[str, str],
    user_id: UserID,
    product_name: str,
    product_api_base_url: str,
) -> None:
    """Performs the actual clone while holding the guest-user GC lock."""
    # Check if copy already exists (idempotent) — access already validated by the controller
    if await _is_copy_finished(app, project_uuid=project_uuid, user_id=user_id, product_name=product_name):
        _logger.debug("Study copy %s already exists for user %s, skipping clone", project_uuid, user_id)
        return

    # New project cloned from template
    await progress.update(message="cloning study document...", percent=0.05)
    try:
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
    except Exception, asyncio.CancelledError:
        # `clone_project_data` commits the copy before its later steps and its uuid is
        # deterministic: a partial copy would be taken for a finished clone by the next dispatch.
        # The cleanup is shielded, so a cancellation of this task cannot interrupt it half way and
        # leave the copy visible; if this task is cancelled again, the cleanup keeps running in
        # the background and the app's fire-and-forget collection drains it.
        cleanup = fire_and_forget_task(
            _delete_copy_or_leave_it_to_gc(app, project_uuid=project_uuid, user_id=user_id, product_name=product_name),
            task_suffix_name=f"dispatch_copy_cleanup_{project_uuid}",
            fire_and_forget_tasks_collection=app[APP_FIRE_AND_FORGET_TASKS_KEY],
        )
        with log_catch(_logger, reraise=False):
            await asyncio.shield(cleanup)
        raise


async def dispatch_study(  # pylint: disable=too-many-arguments
    progress: TaskProgress,
    *,
    app: web.Application,
    study_id: str,
    user_id: UserID,
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
        web.HTTPServiceUnavailable: if a copy left by a failed clone is being deleted
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
            web.HTTPServiceUnavailable,
        ),
        app=app,
    )
