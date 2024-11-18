import logging

from fastapi import FastAPI
from servicelib.logging_utils import log_context
from settings_library.redis import RedisDatabase

from ...core.errors import ConfigurationError
from ...core.settings import AppSettings
from ..dask_clients_pool import DaskClientsPool
from ..db import get_db_engine
from ..rabbitmq import get_rabbitmq_client, get_rabbitmq_rpc_client
from ..redis import get_redis_client_manager
from ._base_scheduler import BaseCompScheduler
from ._dask_scheduler import DaskScheduler

_logger = logging.getLogger(__name__)


async def create_from_db(app: FastAPI) -> BaseCompScheduler:
    scheduler = create_scheduler(app)
    await scheduler.restore_scheduling_from_db()
    return scheduler


def create_scheduler(app: FastAPI) -> BaseCompScheduler:
    if not hasattr(app.state, "engine"):
        msg = "Database connection is missing. Please check application configuration."
        raise ConfigurationError(msg)

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
            db_engine=get_db_engine(app),
            service_runtime_heartbeat_interval=app_settings.SERVICE_TRACKING_HEARTBEAT,
        )
