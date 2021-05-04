# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments

from typing import Dict, Callable
from yarl import URL
from uuid import uuid4


import pytest
import sqlalchemy as sa

from models_library.projects import ProjectAtDB
from starlette.testclient import TestClient
from models_library.settings.rabbit import RabbitConfig
from models_library.settings.redis import RedisConfig


pytest_simcore_core_services_selection = [
    "director",
    "redis",
    "rabbit",
    "postgres",
]
pytest_simcore_ops_services_selection = ["adminer"]


@pytest.fixture(autouse=True)
def minimal_configuration(
    httpbin_service: Dict,
    httpbin_dynamic_sidecar_service: Dict,
    httpbin_dynamic_sidecar_compose_service: Dict,
    redis_service: RedisConfig,
    postgres_db: sa.engine.Engine,
    postgres_host_config: Dict[str, str],
    rabbit_service: RabbitConfig,
    simcore_services: Dict[str, URL],
):
    pass


@pytest.fixture
def httpbins_project(
    project: Callable,
    redis_service: RedisConfig,
    postgres_db: sa.engine.Engine,
    postgres_host_config: Dict[str, str],
    rabbit_service: RabbitConfig,
    httpbin_service: Dict,
    httpbin_dynamic_sidecar_service: Dict,
    httpbin_dynamic_sidecar_compose_service: Dict,
) -> ProjectAtDB:
    def _str_uuid() -> str:
        return str(uuid4())

    return project(
        workbench={
            _str_uuid(): {
                "key": httpbin_service["image"]["name"],
                "version": httpbin_service["image"]["tag"],
                "label": "legacy dynamic service",
            },
            _str_uuid(): {
                "key": httpbin_dynamic_sidecar_service["image"]["name"],
                "version": httpbin_dynamic_sidecar_service["image"]["tag"],
                "label": "dynamic sidecar",
            },
            _str_uuid(): {
                "key": httpbin_dynamic_sidecar_compose_service["image"]["name"],
                "version": httpbin_dynamic_sidecar_compose_service["image"]["tag"],
                "label": "dynamic sidecar with docker compose spec",
            },
        }
    )


async def test_legacy_and_dynamic_sidecar_run(
    client: TestClient, httpbins_project: ProjectAtDB
):
    """
    The test will start 3 dynamic services in the same project and check
    that the legacy and the 2 new dynamic-sidecar boot properly.

    1. Creates a project containing the following services:
    - httpbin
    - httpbin-dynamic-sidecar
    - httpbin-dynamic-sidecar-compose

    2. Starts the nodes in the project
    3. Checks for the status of the project simulating the frontend
    4. When all services are up and running checks they reply correctly tot the API
    """
    # the calls are routed through director-v1

    # TODO: implementation as mentioned above

    assert True