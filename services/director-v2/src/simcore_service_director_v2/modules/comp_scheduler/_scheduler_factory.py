import logging

from fastapi import FastAPI
from servicelib.logging_utils import log_context
from settings_library.redis import RedisDatabase

from ...core.errors import ConfigurationError
from ...core.settings import AppSettings
from ...models.comp_runs import CompRunsAtDB
from ...utils.comp_scheduler import SCHEDULED_STATES
from ..dask_clients_pool import DaskClientsPool
from ..db.repositories.comp_runs import CompRunsRepository
from ..rabbitmq import get_rabbitmq_client, get_rabbitmq_rpc_client
from ..redis import get_redis_client_manager
from ._base_scheduler import BaseCompScheduler, ScheduledPipelineParams
from ._dask_scheduler import DaskScheduler

_logger = logging.getLogger(__name__)


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

    _logger.debug(
        "Following scheduled comp_runs found still to be scheduled: %s",
        runs if runs else "NONE",
    )

    with log_context(
        _logger, logging.INFO, msg="Creating Dask-based computational scheduler"
    ):
        app_settings: AppSettings = app.state.settings
        return DaskScheduler(
            settings=app_settings.DIRECTOR_V2_COMPUTATIONAL_BACKEND,
            dask_clients_pool=DaskClientsPool.instance(app),
            rabbitmq_client=get_rabbitmq_client(app),
            rabbitmq_rpc_client=get_rabbitmq_rpc_client(app),
            redis_client=get_redis_client_manager(app).client(RedisDatabase.LOCKS),
            db_engine=db_engine,
            scheduled_pipelines={
                (r.user_id, r.project_uuid, r.iteration): ScheduledPipelineParams()
                for r in runs
            },
            service_runtime_heartbeat_interval=app_settings.SERVICE_TRACKING_HEARTBEAT,
        )
