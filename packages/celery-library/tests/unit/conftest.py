from collections.abc import AsyncIterator, Awaitable, Callable
from functools import partial
from typing import Final

import pytest
from asgi_lifespan import LifespanManager
from celery import Celery
from celery.contrib.testing.worker import TestWorkController, start_worker
from celery.signals import worker_init, worker_shutdown
from celery.worker.worker import WorkController
from celery_library import setup_celery_client
from celery_library.routes.rpc import router as async_jobs_router
from celery_library.signals import on_worker_init, on_worker_shutdown
from celery_library.utils import get_celery_worker
from celery_library.worker import CeleryTaskWorker
from faker import Faker
from fastapi import FastAPI
from models_library.products import ProductName
from models_library.rabbitmq_basic_types import RPCNamespace
from models_library.users import UserID
from pydantic import TypeAdapter
from servicelib.rabbitmq import RabbitMQRPCClient
from settings_library.celery import CelerySettings
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisSettings

pytest_simcore_core_services_selection = [
    "rabbit",
    "redis",
    "postgres",
]

pytest_plugins = [
    "pytest_simcore.docker_compose",
    "pytest_simcore.docker_swarm",
    "pytest_simcore.rabbit_service",
    "pytest_simcore.redis_service",
    "pytest_simcore.repository_paths",
]

_LIFESPAN_TIMEOUT: Final[int] = 10


@pytest.fixture
def rpc_namespace() -> RPCNamespace:
    return TypeAdapter(RPCNamespace).validate_python("test")


@pytest.fixture
def celery_settings(
    rabbit_service: RabbitSettings,
    redis_service: RedisSettings,
) -> CelerySettings:
    return CelerySettings.create_from_envs()


@pytest.fixture
async def initialized_fast_api(
    rabbitmq_rpc_client: Callable[[str], Awaitable[RabbitMQRPCClient]],
    celery_settings: CelerySettings,
    rpc_namespace: RPCNamespace,
) -> AsyncIterator[FastAPI]:
    app = FastAPI(
        title="master_fastapi_app",
        description="Service that manages osparc storage backend",
        version="0.0.0",
    )

    setup_celery_client(app, celery_settings=celery_settings)
    rpc_client = await rabbitmq_rpc_client("celery_test_client")
    app.state.rabbitmq_rpc_client = rpc_client

    async def startup() -> None:
        rpc_server = app.state.rabbitmq_rpc_client
        assert isinstance(rpc_server, RabbitMQRPCClient)
        await rpc_server.register_router(async_jobs_router, rpc_namespace, app)

    app.add_event_handler("startup", startup)

    async with LifespanManager(
        app, startup_timeout=_LIFESPAN_TIMEOUT, shutdown_timeout=_LIFESPAN_TIMEOUT
    ):
        yield app


@pytest.fixture
def register_celery_tasks() -> Callable[[Celery], None]:
    """override if tasks are needed"""

    def _(celery_app: Celery) -> None: ...

    return _


@pytest.fixture
async def celery_worker_controller(
    celery_settings: CelerySettings,
    celery_app: Celery,
    register_celery_tasks: Callable[[Celery], None],
) -> AsyncIterator[TestWorkController]:

    def _create_app() -> FastAPI:

        return FastAPI(
            title="worker_fastapi_app",
            description="Test application for celery_library",
            version="0.0.0",
        )

    def _on_worker_init_wrapper(sender: WorkController, **_kwargs) -> None:
        return partial(on_worker_init, _create_app, celery_settings)(sender, **_kwargs)

    worker_init.connect(_on_worker_init_wrapper)
    worker_shutdown.connect(on_worker_shutdown)

    register_celery_tasks(celery_app)

    with start_worker(
        celery_app,
        pool="threads",
        concurrency=1,
        loglevel="info",
        perform_ping_check=False,
        queues="default,cpu_bound",
    ) as worker:
        yield worker


@pytest.fixture
def with_storage_celery_worker(
    celery_worker_controller: TestWorkController,
) -> CeleryTaskWorker:
    assert isinstance(celery_worker_controller.app, Celery)
    return get_celery_worker(celery_worker_controller.app)


@pytest.fixture
def user_id(faker: Faker) -> UserID:
    return TypeAdapter(UserID).validate_python(faker.pyint(min_value=1, max_value=1000))


@pytest.fixture
def product_name() -> ProductName:
    return TypeAdapter(ProductName).validate_python("pytest-product")
