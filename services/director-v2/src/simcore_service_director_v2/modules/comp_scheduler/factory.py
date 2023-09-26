import logging

from fastapi import FastAPI
from models_library.clusters import DEFAULT_CLUSTER_ID
from simcore_service_director_v2.core.settings import AppSettings

from ...core.errors import ConfigurationError
from ...models.comp_runs import CompRunsAtDB
from ...modules.dask_clients_pool import DaskClientsPool
from ...modules.rabbitmq import get_rabbitmq_client, get_rabbitmq_rpc_client
from ...utils.comp_scheduler import SCHEDULED_STATES
from ..db.repositories.comp_runs import CompRunsRepository
from .base_scheduler import BaseCompScheduler, ScheduledPipelineParams
from .dask_scheduler import DaskScheduler

logger = logging.getLogger(__name__)


async def create_from_db(app: FastAPI) -> BaseCompScheduler:
    if not hasattr(app.state, "engine"):
        msg = "Database connection is missing. Please check application configuration."
        raise ConfigurationError(msg)
    db_engine = app.state.engine
    runs_repository = CompRunsRepository.instance(db_engine)

    # get currently scheduled runs
    runs: list[CompRunsAtDB] = await runs_repository.list(
        filter_by_state=SCHEDULED_STATES
    )

    logger.debug(
        "Following scheduled comp_runs found still to be scheduled: %s",
        runs if runs else "NONE",
    )

    logger.info("Creating Dask-based scheduler...")
    app_settings: AppSettings = app.state.settings
    return DaskScheduler(
        settings=app_settings.DIRECTOR_V2_COMPUTATIONAL_BACKEND,
        dask_clients_pool=DaskClientsPool.instance(app),
        rabbitmq_client=get_rabbitmq_client(app),
        rabbitmq_rpc_client=get_rabbitmq_rpc_client(app),
        db_engine=db_engine,
        scheduled_pipelines={
            (r.user_id, r.project_uuid, r.iteration): ScheduledPipelineParams(
                cluster_id=r.cluster_id
                if r.cluster_id is not None
                else DEFAULT_CLUSTER_ID,
                run_metadata=r.metadata,
                mark_for_cancellation=False,
                use_on_demand_clusters=r.use_on_demand_clusters,
            )
            for r in runs
        },
        service_runtime_heartbeat_interval=app_settings.SERVICE_TRACKING_HEARTBEAT,
    )
