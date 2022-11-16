import logging
from typing import cast

from fastapi import FastAPI
from models_library.clusters import DEFAULT_CLUSTER_ID
from simcore_service_director_v2.modules.dask_clients_pool import DaskClientsPool

from ...core.errors import ConfigurationError
from ...models.domains.comp_runs import CompRunsAtDB
from ...modules.rabbitmq import get_rabbitmq_client
from ...utils.scheduler import SCHEDULED_STATES, get_repository
from ..db.repositories.comp_runs import CompRunsRepository
from .base_scheduler import BaseCompScheduler, ScheduledPipelineParams
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
    runs: list[CompRunsAtDB] = await runs_repository.list(
        filter_by_state=SCHEDULED_STATES
    )

    logger.debug(
        "Following scheduled comp_runs found still to be scheduled: %s",
        runs if runs else "NONE",
    )

    logger.info("Creating Dask-based scheduler...")
    return DaskScheduler(
        settings=app.state.settings.DIRECTOR_V2_COMPUTATIONAL_BACKEND,
        dask_clients_pool=DaskClientsPool.instance(app),
        rabbitmq_client=get_rabbitmq_client(app),
        db_engine=db_engine,
        scheduled_pipelines={
            (r.user_id, r.project_uuid, r.iteration): ScheduledPipelineParams(
                cluster_id=r.cluster_id
                if r.cluster_id is not None
                else DEFAULT_CLUSTER_ID,
                mark_for_cancellation=False,
            )
            for r in runs
        },
    )
