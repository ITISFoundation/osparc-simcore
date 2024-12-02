import logging

from fastapi import FastAPI
from servicelib.logging_utils import log_context
from settings_library.redis import RedisDatabase

from ...core.settings import AppSettings
from ..dask_clients_pool import DaskClientsPool
from ..db import get_db_engine
from ..rabbitmq import get_rabbitmq_client, get_rabbitmq_rpc_client
from ..redis import get_redis_client_manager
from ._scheduler_base import BaseCompScheduler
from ._scheduler_dask import DaskScheduler

_logger = logging.getLogger(__name__)


def create_scheduler(app: FastAPI) -> BaseCompScheduler:
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
