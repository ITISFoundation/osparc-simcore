# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from collections.abc import Awaitable, Callable
from typing import Any

import pytest
import sqlalchemy as sa
from faker import Faker
from fastapi import FastAPI
from models_library.projects import ProjectAtDB
from models_library.projects_nodes_io import NodeID
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_postgres_database.utils_projects_nodes import ProjectNodesNodeNotFoundError
from simcore_service_director_v2.modules.db.repositories.projects import (
    ProjectsRepository,
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
            "parent": None,
            "thumbnail": "",
        }
    }


@pytest.fixture()
async def project(
    mock_env: EnvVarsDict,
    create_registered_user: Callable[..., dict],
    product_db: dict[str, Any],
    project: Callable[..., Awaitable[ProjectAtDB]],
    workbench: dict[str, Any],
) -> ProjectAtDB:
    return await project(create_registered_user(), workbench=workbench)


async def test_is_node_present_in_workbench(
    initialized_app: FastAPI, project: ProjectAtDB, faker: Faker
):
    project_repository = get_repository(initialized_app, ProjectsRepository)

    for node_uuid in project.workbench:
        assert (
            await project_repository.is_node_present_in_workbench(
                project_id=project.uuid, node_uuid=NodeID(node_uuid)
            )
            is True
        )

    not_existing_node = faker.uuid4(cast_to=None)
    assert not_existing_node not in project.workbench
    assert (
        await project_repository.is_node_present_in_workbench(
            project_id=project.uuid, node_uuid=not_existing_node
        )
        is False
    )

    not_existing_project = faker.uuid4(cast_to=None)
    assert not_existing_project != project.uuid
    assert (
        await project_repository.is_node_present_in_workbench(
            project_id=not_existing_project, node_uuid=not_existing_node
        )
        is False
    )


async def test_get_project_id_from_node(
    initialized_app: FastAPI, project: ProjectAtDB, faker: Faker
):
    project_repository = get_repository(initialized_app, ProjectsRepository)
    for node_uuid in project.workbench:
        assert (
            await project_repository.get_project_id_from_node(NodeID(node_uuid))
            == project.uuid
        )

    not_existing_node_id = faker.uuid4(cast_to=None)
    with pytest.raises(ProjectNodesNodeNotFoundError):
        await project_repository.get_project_id_from_node(not_existing_node_id)
