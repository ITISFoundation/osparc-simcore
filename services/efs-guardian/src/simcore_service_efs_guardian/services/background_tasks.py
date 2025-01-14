import logging
from datetime import UTC, datetime

from fastapi import FastAPI
from models_library.projects import ProjectID
from models_library.projects_state import ProjectStatus
from servicelib.logging_utils import log_context
from servicelib.project_lock import lock_project
from simcore_postgres_database.utils_projects import (
    DBProjectNotFoundError,
    ProjectsRepo,
)

from ..core.settings import ApplicationSettings
from .efs_manager import EfsManager
from .modules.redis import get_redis_lock_client

_logger = logging.getLogger(__name__)


async def removal_policy_task(app: FastAPI) -> None:
    _logger.info("Removal policy task started")

    app_settings: ApplicationSettings = app.state.settings
    assert app_settings  # nosec
    efs_manager: EfsManager = app.state.efs_manager

    base_start_timestamp = datetime.now(tz=UTC)

    efs_project_ids: list[
        ProjectID
    ] = await efs_manager.list_projects_across_whole_efs()
    _logger.info(
        "Number of projects that are currently in the EFS file system: %s",
        len(efs_project_ids),
    )

    projects_repo = ProjectsRepo(app.state.engine)
    for project_id in efs_project_ids:
        try:
            _project_last_change_date = (
                await projects_repo.get_project_last_change_date(project_id)
            )
        except DBProjectNotFoundError:
            _logger.info(
                "Project %s not found. Removing EFS data for project {project_id} started",
                project_id,
            )
            await efs_manager.remove_project_efs_data(project_id)
        if (
            _project_last_change_date
            < base_start_timestamp
            - app_settings.EFS_REMOVAL_POLICY_TASK_AGE_LIMIT_TIMEDELTA
        ):
            with log_context(
                _logger,
                logging.INFO,
                msg=f"Removing data for project {project_id} started, project last change date {_project_last_change_date}, efs removal policy task age limit timedelta {app_settings.EFS_REMOVAL_POLICY_TASK_AGE_LIMIT_TIMEDELTA}",
            ):
                async with lock_project(
                    get_redis_lock_client(app),
                    project_uuid=project_id,
                    status=ProjectStatus.MAINTAINING,
                ):
                    await efs_manager.remove_project_efs_data(project_id)
