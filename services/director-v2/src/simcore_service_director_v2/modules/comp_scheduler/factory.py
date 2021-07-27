import logging
from typing import List, cast

from fastapi import FastAPI

from ...core.errors import ConfigurationError
from ...models.domains.comp_runs import CompRunsAtDB
from ...utils.scheduler import SCHEDULED_STATES, get_repository
from ..db.repositories.comp_runs import CompRunsRepository
from .base_scheduler import BaseCompScheduler

logger = logging.getLogger(__name__)


async def create_from_db(app: FastAPI) -> BaseCompScheduler:
    if not hasattr(app.state, "engine"):
        raise ConfigurationError(
            "Database connection is missing. Please check application configuration."
        )
    db_engine = app.state.engine
    runs_repository: CompRunsRepository = cast(
        CompRunsRepository, get_repository(db_engine, CompRunsRepository)
    )

    # get currently scheduled runs
    runs: List[CompRunsAtDB] = await runs_repository.list(
        filter_by_state=SCHEDULED_STATES
    )

    logger.debug(
        "Following scheduled comp_runs found still to be scheduled: %s",
        runs if runs else "NONE",
    )

    # check which scheduler to start
    if (
        app.state.settings.CELERY_SCHEDULER.DIRECTOR_V2_CELERY_SCHEDULER_ENABLED
        and not app.state.settings.DIRECTOR_V2_DEV_FEATURES_ENABLED
    ):
        logger.info("Creating Celery-based scheduler...")
        from ..celery import CeleryClient
        from .celery_scheduler import CeleryScheduler

        return CeleryScheduler(
            settings=app.state.settings.CELERY_SCHEDULER,
            db_engine=db_engine,
            celery_client=CeleryClient.instance(app),
            scheduled_pipelines={
                (r.user_id, r.project_uuid, r.iteration) for r in runs
            },
        )
    from ..dask_client import DaskClient
    from .dask_scheduler import DaskScheduler

    logger.info("Creating Dask-based scheduler...")
    return DaskScheduler(
        settings=app.state.settings.DASK_SCHEDULER,
        dask_client=DaskClient.instance(app),
        db_engine=db_engine,
        scheduled_pipelines={(r.user_id, r.project_uuid, r.iteration) for r in runs},
    )
