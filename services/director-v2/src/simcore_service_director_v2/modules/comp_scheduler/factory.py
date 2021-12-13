import logging
from typing import List, cast

from fastapi import FastAPI

from ...core.errors import ConfigurationError
from ...models.domains.comp_runs import CompRunsAtDB
from ...modules.rabbitmq import RabbitMQClient
from ...utils.scheduler import SCHEDULED_STATES, get_repository
from ..celery import CeleryClient
from ..dask_client import DaskClient
from ..db.repositories.comp_runs import CompRunsRepository
from .base_scheduler import BaseCompScheduler, ScheduledPipelineParams
from .celery_scheduler import CeleryScheduler
from .dask_scheduler import DaskScheduler

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

    # TODO: here we need to persist the pipeline stopping part

    # check which scheduler to start
    if app.state.settings.CELERY_SCHEDULER.DIRECTOR_V2_CELERY_SCHEDULER_ENABLED:
        logger.info("Creating Celery-based scheduler...")

        return CeleryScheduler(
            settings=app.state.settings.CELERY_SCHEDULER,
            db_engine=db_engine,
            default_cluster_id=app.state.settings.DASK_SCHEDULER.DASK_DEFAULT_CLUSTER_ID,
            celery_client=CeleryClient.instance(app),
            scheduled_pipelines={
                (r.user_id, r.project_uuid, r.iteration): ScheduledPipelineParams(
                    cluster_id=r.cluster_id
                    if r.cluster_id is not None
                    else app.state.settings.DASK_SCHEDULER.DASK_DEFAULT_CLUSTER_ID,
                    mark_for_cancellation=False,
                )
                for r in runs
            },
        )

    logger.info("Creating Dask-based scheduler...")
    return DaskScheduler(
        settings=app.state.settings.DASK_SCHEDULER,
        dask_client=DaskClient.instance(app),
        rabbitmq_client=RabbitMQClient.instance(app),
        db_engine=db_engine,
        default_cluster_id=app.state.settings.DASK_SCHEDULER.DASK_DEFAULT_CLUSTER_ID,
        scheduled_pipelines={
            (r.user_id, r.project_uuid, r.iteration): ScheduledPipelineParams(
                cluster_id=r.cluster_id
                if r.cluster_id is not None
                else app.state.settings.DASK_SCHEDULER.DASK_DEFAULT_CLUSTER_ID,
                mark_for_cancellation=False,
            )
            for r in runs
        },
    )
