import logging

from celery_library.rpc import _async_jobs
from fastapi import FastAPI
from models_library.api_schemas_storage import STORAGE_RPC_NAMESPACE
from servicelib.logging_utils import log_context
from servicelib.rabbitmq import RPCRouter
from simcore_service_storage.modules.celery import get_task_manager_from_app

from ...modules.rabbitmq import get_rabbitmq_rpc_server
from . import _paths, _simcore_s3

_logger = logging.getLogger(__name__)


ROUTERS: list[RPCRouter] = [
    _async_jobs.router,
    _paths.router,
    _simcore_s3.router,
]


def setup_rpc_routes(app: FastAPI) -> None:
    async def startup() -> None:
        with log_context(
            _logger,
            logging.INFO,
            msg="Storage startup RPC API Routes",
        ):
            rpc_server = get_rabbitmq_rpc_server(app)
            task_manager = get_task_manager_from_app(app)
            for router in ROUTERS:
                await rpc_server.register_router(
                    router, STORAGE_RPC_NAMESPACE, task_manager=task_manager
                )

    app.add_event_handler("startup", startup)
