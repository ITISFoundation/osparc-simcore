import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from datetime import timedelta

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State
from temporalio.client import Client
from temporalio.worker import Worker

from ...core.settings import ApplicationSettings
from ._dependencies import get_temporalio_client, get_workflow_registry
from ._engine import WorkflowEngine
from ._health_check import TemporalHealthCheck, wait_till_temporalio_is_responsive
from ._heartbeat import HeartbeatInterceptor
from ._registry import WorkflowRegistry

_logger = logging.getLogger(__name__)


async def _temporalio_client_lifespan(app: FastAPI) -> AsyncIterator[State]:
    settings: ApplicationSettings = app.state.settings
    temporalio_settings = settings.DYNAMIC_SCHEDULER_TEMPORALIO_SETTINGS

    client = await Client.connect(
        temporalio_settings.target_host,
        namespace=temporalio_settings.TEMPORALIO_NAMESPACE,
    )
    app.state.temporalio_client = client

    await wait_till_temporalio_is_responsive(client)

    health_check = TemporalHealthCheck(client)
    await health_check.setup()
    app.state.temporalio_health_check = health_check

    yield {}

    await health_check.shutdown()


async def _temporalio_worker_lifespan(app: FastAPI) -> AsyncIterator[State]:
    settings: ApplicationSettings = app.state.settings
    temporalio_settings = settings.DYNAMIC_SCHEDULER_TEMPORALIO_SETTINGS
    client = get_temporalio_client(app)
    registry = get_workflow_registry(app)

    worker = Worker(
        client,
        task_queue=temporalio_settings.TEMPORALIO_TASK_QUEUE,
        workflows=registry.get_temporalio_workflows(),
        activities=registry.get_temporalio_activities(),
        interceptors=[HeartbeatInterceptor()],
        graceful_shutdown_timeout=timedelta(seconds=temporalio_settings.TEMPORALIO_WORKER_GRACEFUL_SHUTDOWN_TIMEOUT_S),
    )

    worker_task = asyncio.create_task(worker.run())
    app.state.temporalio_worker = worker
    app.state.temporalio_worker_task = worker_task

    yield {}

    await worker.shutdown()
    worker_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await worker_task


async def _workflow_engine_lifespan(app: FastAPI) -> AsyncIterator[State]:
    app.state.workflow_engine = WorkflowEngine(app)
    yield {}


async def t_scheduler_registry_lifespan(app: FastAPI) -> AsyncIterator[State]:
    app.state.workflow_registry = WorkflowRegistry()
    yield {}


t_scheduler_lifespan_manager = LifespanManager()
t_scheduler_lifespan_manager.add(_temporalio_client_lifespan)
t_scheduler_lifespan_manager.add(_temporalio_worker_lifespan)
t_scheduler_lifespan_manager.add(_workflow_engine_lifespan)
