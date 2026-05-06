"""Background driver for the `nodes_pending_deletion` outbox.

For each pending row this service retries the node-storage cleanup that did
not finish during the original `_remove_service_and_its_data_folders` call.

If the storage step fails, the outbox row is left behind and `attempts` /
`last_error` are bumped. Rows whose `attempts` exceed `max_attempts` are
skipped (dead-letter) so they can be inspected by ops.

Mirror of `_pending_deletion_service.py` for project-level deletions, but
keyed on `(project_uuid, node_id)`.
"""

import logging

from aiohttp import web
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.users import UserID
from servicelib.logging_utils import log_context

from ..storage.api import delete_project_via_celery
from . import _node_pending_deletion_repository
from ._projects_repository_legacy import ProjectDBAPI
from .exceptions import ProjectNotFoundError

_logger = logging.getLogger(__name__)


async def _retry_one(
    app: web.Application,
    *,
    project_uuid: ProjectID,
    node_id: NodeID,
    user_id: UserID,
) -> None:
    db: ProjectDBAPI = ProjectDBAPI.get_from_app_context(app)

    try:
        product_name = await db.get_project_product(project_uuid)
    except ProjectNotFoundError:
        _logger.warning(
            "Project %s already gone from DB; removing orphan node outbox row for node=%s",
            project_uuid,
            node_id,
        )
        await _node_pending_deletion_repository.delete_pending_deletion(app, project_uuid=project_uuid, node_id=node_id)
        return

    try:
        await delete_project_via_celery(
            app,
            user_id=user_id,
            product_name=product_name,
            project_id=project_uuid,
            node_id=node_id,
        )
    except Exception as exc:  # pylint: disable=broad-except
        await _node_pending_deletion_repository.record_failed_attempt(
            app,
            project_uuid=project_uuid,
            node_id=node_id,
            error_message=f"{exc}",
        )
        _logger.warning(
            "Storage cleanup retry failed for project=%s node=%s user=%s: %s",
            project_uuid,
            node_id,
            user_id,
            exc,
        )
        return

    await _node_pending_deletion_repository.delete_pending_deletion(app, project_uuid=project_uuid, node_id=node_id)
    _logger.info(
        "Recovered pending node deletion: project=%s node=%s user=%s",
        project_uuid,
        node_id,
        user_id,
    )


async def retry_pending_deletions(
    app: web.Application,
    *,
    batch_size: int = 50,
    max_attempts: int = 10,
) -> None:
    """Drive a single pass over the `nodes_pending_deletion` outbox.

    Skips rows where `requested_by IS NULL` (originating user was deleted) and
    rows whose `attempts >= max_attempts` (dead-letter; ops must inspect).
    """
    rows = await _node_pending_deletion_repository.list_pending_deletions(app, limit=batch_size)
    if not rows:
        return

    with log_context(
        _logger,
        logging.INFO,
        f"Retrying {len(rows)} pending node deletions",
    ):
        for row in rows:
            project_uuid_str = row["project_uuid"]
            node_id_str = row["node_id"]
            user_id = row["requested_by"]
            attempts = row["attempts"]

            if user_id is None:
                _logger.warning(
                    "Skipping pending node deletion for project=%s node=%s:"
                    " requested_by is NULL (originating user was deleted);"
                    " ops must reconcile manually",
                    project_uuid_str,
                    node_id_str,
                )
                continue

            if attempts >= max_attempts:
                _logger.error(
                    "Dead-lettering pending node deletion for project=%s node=%s after %d attempts; last_error=%r",
                    project_uuid_str,
                    node_id_str,
                    attempts,
                    row["last_error"],
                )
                continue

            await _retry_one(
                app,
                project_uuid=ProjectID(project_uuid_str),
                node_id=NodeID(node_id_str),
                user_id=user_id,
            )
