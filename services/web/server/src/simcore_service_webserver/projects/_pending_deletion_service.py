"""Background driver for the `projects_pending_deletion` outbox.

For each pending row this service retries the cleanup that did not finish
during the original `_crud_api_delete._delete_project` call:

  1. delete the project's data from storage (S3 + file_meta_data)
  2. delete the `projects` row from the webserver DB
  3. remove the outbox row

If any step fails, the outbox row is left behind and `attempts` / `last_error`
are bumped via `record_failed_attempt`. Rows whose `attempts` exceed
`max_attempts` are skipped (dead-letter) so they can be inspected by ops.
"""

import logging

from aiohttp import web
from models_library.projects import ProjectID
from models_library.users import UserID
from servicelib.logging_utils import log_context

from ..storage.api import delete_project_via_celery
from . import _pending_deletion_repository
from ._projects_repository_legacy import ProjectDBAPI
from .exceptions import ProjectNotFoundError

_logger = logging.getLogger(__name__)


async def _retry_one(
    app: web.Application,
    *,
    project_uuid: ProjectID,
    user_id: UserID,
) -> None:
    db: ProjectDBAPI = ProjectDBAPI.get_from_app_context(app)

    try:
        product_name = await db.get_project_product(project_uuid)
    except ProjectNotFoundError:
        _logger.warning(
            "Project %s already gone from DB; removing orphan outbox row",
            project_uuid,
        )
        await _pending_deletion_repository.delete_pending_deletion(app, project_uuid=project_uuid)
        return

    try:
        await delete_project_via_celery(
            app,
            user_id=user_id,
            product_name=product_name,
            project_id=project_uuid,
        )
    except Exception as exc:  # pylint: disable=broad-except
        await _pending_deletion_repository.record_failed_attempt(app, project_uuid=project_uuid, error_message=f"{exc}")
        _logger.warning(
            "Storage cleanup retry failed for project=%s user=%s: %s",
            project_uuid,
            user_id,
            exc,
        )
        return

    try:
        await db.delete_project(user_id, f"{project_uuid}")
    except Exception as exc:  # pylint: disable=broad-except
        await _pending_deletion_repository.record_failed_attempt(
            app, project_uuid=project_uuid, error_message=f"db.delete_project: {exc}"
        )
        _logger.warning(
            "DB delete_project retry failed for project=%s user=%s: %s",
            project_uuid,
            user_id,
            exc,
        )
        return

    await _pending_deletion_repository.delete_pending_deletion(app, project_uuid=project_uuid)
    _logger.info("Recovered pending deletion: project=%s user=%s", project_uuid, user_id)


async def retry_pending_deletions(
    app: web.Application,
    *,
    batch_size: int = 50,
    max_attempts: int = 10,
) -> None:
    """Drive a single pass over the `projects_pending_deletion` outbox.

    Skips rows where `requested_by IS NULL` (originating user was deleted) and
    rows whose `attempts >= max_attempts` (dead-letter; ops must inspect).
    """
    rows = await _pending_deletion_repository.list_pending_deletions(app, limit=batch_size)
    if not rows:
        return

    with log_context(
        _logger,
        logging.INFO,
        f"Retrying {len(rows)} pending project deletions",
    ):
        for row in rows:
            project_uuid_str = row["project_uuid"]
            user_id = row["requested_by"]
            attempts = row["attempts"]

            if user_id is None:
                _logger.warning(
                    "Skipping pending deletion for project=%s: requested_by is NULL"
                    " (originating user was deleted); ops must reconcile manually",
                    project_uuid_str,
                )
                continue

            if attempts >= max_attempts:
                _logger.error(
                    "Dead-lettering pending deletion for project=%s after %d attempts; last_error=%r",
                    project_uuid_str,
                    attempts,
                    row["last_error"],
                )
                continue

            await _retry_one(app, project_uuid=ProjectID(project_uuid_str), user_id=user_id)
