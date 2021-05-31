# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


import urllib
from asyncio import BaseEventLoop
from typing import Dict

import pytest
from _pytest.monkeypatch import MonkeyPatch
from asgi_lifespan import LifespanManager
from httpx import AsyncClient
from simcore_service_catalog.meta import api_vtag

pytest_simcore_core_services_selection = [
    "postgres",
]


@pytest.fixture(autouse=True)
def minimal_configuration(
    docker_registry: str,
    postgres_host_config: Dict[str, str],
    monkeypatch: MonkeyPatch,
):
    monkeypatch.setenv("DIRECTOR_HOST", "http://director_host_node_defined")
    monkeypatch.setenv("SC_BOOT_MODE", "debug-ptvsd")
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("background_task_enabled", "false")


@pytest.fixture
async def test_client(loop: BaseEventLoop) -> AsyncClient:
    from simcore_service_catalog.main import the_app

    async with AsyncClient(
        app=the_app, base_url=f"http://test/{api_vtag}"
    ) as client, LifespanManager(the_app):
        yield client


@pytest.fixture
def service_key(sleeper_service: Dict[str, str]) -> str:
    return sleeper_service["schema"]["key"]


@pytest.fixture
def service_version(sleeper_service: Dict[str, str]) -> str:
    return sleeper_service["schema"]["version"]


async def test_registry_labels(
    test_client: AsyncClient, service_key: str, service_version: str
) -> None:
    url = f"/registry/{urllib.parse.quote_plus(service_key)}/{service_version}:labels"
    response = await test_client.get(url)

    assert response.status_code == 200, response.text
    assert response.json() == {
        "io.simcore.authors": '{"authors": [{"name": "Manuel Guidon", "email": "guidon@itis.ethz.ch", "affiliation": "ITIS Foundation"}]}',
        "io.simcore.contact": '{"contact": "guidon@itis.ethz.ch"}',
        "io.simcore.description": '{"description": "Solver that sleeps for a random amount of seconds"}',
        "io.simcore.inputs": '{"inputs": {"in_1": {"displayOrder": 1, "label": "Number of seconds to sleep", "description": "Number of seconds to sleep", "type": "data:*/*", "fileToKeyMap": {"in_1": "in_1"}}, "in_2": {"displayOrder": 2, "label": "Number of seconds to sleep", "description": "Number of seconds to sleep", "type": "integer", "defaultValue": 2}}}',
        "io.simcore.key": '{"key": "simcore/services/comp/itis/sleeper"}',
        "io.simcore.name": '{"name": "sleeper"}',
        "io.simcore.outputs": '{"outputs": {"out_1": {"displayOrder": 1, "label": "Number of seconds to sleep", "description": "Number of seconds to sleep", "type": "data:*/*", "fileToKeyMap": {"out_1": "out_1"}}, "out_2": {"displayOrder": 2, "label": "Number of seconds to sleep", "description": "Number of seconds to sleep", "type": "integer"}}}',
        "io.simcore.type": '{"type": "computational"}',
        "io.simcore.version": '{"version": "1.0.0"}',
    }


async def test_registry_repositories(test_client: AsyncClient) -> None:
    response = await test_client.get("/registry/repository")
    assert response.status_code == 200, response.text
    assert set(response.json()) == {"hello-world", "simcore/services/comp/itis/sleeper"}


async def test_registry_tags(test_client: AsyncClient, service_key: str) -> None:
    url = f"/registry/{urllib.parse.quote_plus(service_key)}:tags"
    response = await test_client.get(url)
    assert response.status_code == 200, response.text
    assert set(response.json()) == {"1.0.0"}
