# pylint:disable=contextmanager-generator-missing-cleanup
# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

import asyncio
from collections.abc import AsyncIterator

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from models_library.api_schemas_dynamic_scheduler.dynamic_services import DynamicServiceStart, DynamicServiceStop
from models_library.projects_nodes_io import NodeID
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.postgres_tools import (
    PostgresTestConfig,
)
from pytest_simcore.helpers.typing_env import EnvVarsDict
from settings_library.docker_api_proxy import DockerApiProxysettings
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisSettings
from simcore_service_dynamic_scheduler.services.p_scheduler import (
    BaseStep,
    InData,
    OutData,
    WorkflowDefinition,
    register_workflow,
    request_present,
)
from sqlalchemy.ext.asyncio import AsyncEngine

pytest_simcore_core_services_selection = [
    "docker-api-proxy",
    "postgres",
    "rabbit",
    "redis",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]


@pytest.fixture
def app_environment(
    app_environment: EnvVarsDict,
    disable_generic_scheduler_lifespan: None,
    postgres_db: sa.engine.Engine,
    postgres_host_config: PostgresTestConfig,
    disable_service_tracker_lifespan: None,
    disable_deferred_manager_lifespan: None,
    disable_notifier_lifespan: None,
    disable_status_monitor_lifespan: None,
    docker_api_proxy_settings: DockerApiProxysettings,
    rabbit_service: RabbitSettings,
    redis_service: RedisSettings,
    monkeypatch: pytest.MonkeyPatch,
) -> EnvVarsDict:
    setenvs_from_dict(
        monkeypatch,
        {
            "POSTGRES_CLIENT_NAME": "test_postgres_client",
            "DOCKER_API_PROXY_HOST": "127.0.0.1",
            "DOCKER_API_PROXY_PORT": "8014",
            "DOCKER_API_PROXY_USER": docker_api_proxy_settings.DOCKER_API_PROXY_USER,
            "DOCKER_API_PROXY_PASSWORD": docker_api_proxy_settings.DOCKER_API_PROXY_PASSWORD.get_secret_value(),
        },
    )
    return app_environment


@pytest.fixture
def engine(app: FastAPI) -> AsyncEngine:
    assert isinstance(app.state.engine, AsyncEngine)
    return app.state.engine


@pytest.fixture(autouse=True)
async def ensure_no_background_task_errors() -> AsyncIterator[None]:
    """Ensures no background asyncio tasks produced unhandled exceptions.

    Hooks the event loop's exception handler on the RUNNING loop
    (same loop as the async test) to intercept 'Task exception was
    never retrieved' errors as they happen during GC.
    """
    collected_exceptions: list[dict] = []

    loop = asyncio.get_running_loop()
    original_handler = loop.get_exception_handler()

    def _custom_exception_handler(loop: asyncio.AbstractEventLoop, context: dict) -> None:
        collected_exceptions.append(context)
        # still call the original/default so logs appear as usual
        if original_handler:
            original_handler(loop, context)
        else:
            loop.default_exception_handler(context)

    loop.set_exception_handler(_custom_exception_handler)

    yield

    loop.set_exception_handler(original_handler)

    assert not collected_exceptions, (
        "TIP: check logs above for more. Background asyncio tasks raised unhandled exceptions:\n"
        + "\n---\n".join(
            f"message={ctx.get('message')}\nexception={ctx.get('exception')!r}\nfuture={ctx.get('future')}"
            for ctx in collected_exceptions
        )
    )


class AStep(BaseStep):
    @classmethod
    async def apply(cls, in_data: InData) -> OutData:
        _ = in_data
        return {}

    @classmethod
    def get_apply_timeout(cls) -> int:
        return 1

    @classmethod
    async def revert(cls, in_data: InData) -> OutData:
        _ = in_data

    @classmethod
    def get_revert_timeout(cls) -> int:
        return 1


async def test_workflow(
    app: FastAPI, node_id: NodeID, dynamic_service_start: DynamicServiceStart, dynamic_service_stop: DynamicServiceStop
) -> None:
    workflow = WorkflowDefinition(initial_context=set(), steps=[(AStep, [])])
    register_workflow(app, "a_workflow", workflow)

    await request_present(app, node_id, dynamic_service_start)

    await asyncio.sleep(5)
