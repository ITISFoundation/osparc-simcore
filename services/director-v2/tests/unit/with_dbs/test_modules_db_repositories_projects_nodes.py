# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from collections.abc import Awaitable, Callable
from typing import Any

import pytest
import sqlalchemy as sa
from faker import Faker
from fastapi import FastAPI
from models_library.projects import ProjectAtDB
from models_library.projects_nodes import Node
from models_library.projects_nodes_io import NodeID
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_director_v2.core.errors import ProjectNodeNotFoundError
from simcore_service_director_v2.modules.db.repositories.projects_nodes import (
    ProjectsNodesRepository,
)
from simcore_service_director_v2.utils.db import get_repository

pytest_simcore_core_services_selection = [
    "postgres",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]


@pytest.fixture
def mock_env(
    monkeypatch: pytest.MonkeyPatch,
    postgres_host_config: dict[str, str],
    mock_env: EnvVarsDict,
    postgres_db: sa.engine.Engine,
    faker: Faker,
) -> EnvVarsDict:
    """overrides unit/conftest:mock_env fixture"""
    env_vars = mock_env.copy()
    env_vars.update(
        {
            "S3_ACCESS_KEY": "12345678",
            "S3_BUCKET_NAME": "simcore",
            "S3_ENDPOINT": "http://172.17.0.1:9001",
            "S3_REGION": faker.pystr(),
            "S3_SECRET_KEY": "12345678",
            "POSTGRES_HOST": postgres_host_config["host"],
            "POSTGRES_USER": postgres_host_config["user"],
            "POSTGRES_PASSWORD": postgres_host_config["password"],
            "POSTGRES_DB": postgres_host_config["database"],
        }
    )
    setenvs_from_dict(monkeypatch, env_vars)
    return env_vars


@pytest.fixture
def workbench() -> dict[str, Any]:
    return {
        "13220a1d-a569-49de-b375-904301af9295": {
            "key": "simcore/services/dynamic/a-nice-one",
            "version": "2.1.4",
            "label": "sleeper",
            "inputsUnits": {},
            "inputNodes": ["38a0d401-af4b-4ea7-ab4c-5005c712a546"],
            "thumbnail": "",
        },
        "38a0d401-af4b-4ea7-ab4c-5005c712a546": {
            "key": "simcore/services/comp/itis/sleeper",
            "version": "1.0.0",
            "label": "another-one",
            "inputsUnits": {},
            "inputNodes": [],
            "thumbnail": "",
        },
    }


@pytest.fixture
async def with_project(
    mock_env: EnvVarsDict,
    create_registered_user: Callable[..., dict],
    with_product: dict[str, Any],
    create_project: Callable[..., Awaitable[ProjectAtDB]],
    workbench: dict[str, Any],
) -> ProjectAtDB:
    return await create_project(create_registered_user(), workbench=workbench)


async def test_exists(initialized_app: FastAPI, with_project: ProjectAtDB, faker: Faker):
    repository = get_repository(initialized_app, ProjectsNodesRepository)

    for node_uuid in with_project.workbench:
        assert await repository.exists(with_project.uuid, NodeID(node_uuid)) is True

    not_existing_node = faker.uuid4(cast_to=None)
    assert not_existing_node not in with_project.workbench
    assert await repository.exists(with_project.uuid, not_existing_node) is False

    not_existing_project = faker.uuid4(cast_to=None)
    assert not_existing_project != with_project.uuid
    assert await repository.exists(not_existing_project, not_existing_node) is False


async def test_get(initialized_app: FastAPI, with_project: ProjectAtDB, faker: Faker):
    repository = get_repository(initialized_app, ProjectsNodesRepository)

    for node_uuid, node_data in with_project.workbench.items():
        node = await repository.get(with_project.uuid, NodeID(node_uuid))
        assert isinstance(node, Node)
        assert node.key == node_data.key
        assert node.version == node_data.version

    not_existing_node = faker.uuid4(cast_to=None)
    with pytest.raises(ProjectNodeNotFoundError):
        await repository.get(with_project.uuid, not_existing_node)


async def test_list_nodes_ids(initialized_app: FastAPI, with_project: ProjectAtDB):
    repository = get_repository(initialized_app, ProjectsNodesRepository)

    node_ids = await repository.list_nodes_ids(with_project.uuid)

    assert sorted(node_ids) == sorted(NodeID(node_uuid) for node_uuid in with_project.workbench)


async def test_get_all(initialized_app: FastAPI, with_project: ProjectAtDB):
    repository = get_repository(initialized_app, ProjectsNodesRepository)

    nodes = await repository.get_all(with_project.uuid)

    assert set(nodes) == set(with_project.workbench)
    for node_uuid, node in nodes.items():
        assert isinstance(node, Node)
        assert node.key == with_project.workbench[node_uuid].key
        assert node.version == with_project.workbench[node_uuid].version
