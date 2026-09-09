# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import pytest
import sqlalchemy as sa
from _helpers import PublishedProject
from faker import Faker
from fastapi import FastAPI
from models_library.projects_nodes_io import NodeID
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_director_v2.core.errors import (
    ComputationalTaskJobIdAlreadySetError,
    ComputationalTaskNotFoundError,
)
from simcore_service_director_v2.models.comp_runs import RunID
from simcore_service_director_v2.modules.db.repositories.comp_tasks import (
    CompTasksRepository,
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


async def test_set_task_job_id_raises_if_already_set(
    initialized_app: FastAPI,
    published_project: PublishedProject,
):
    """set_task_job_id must never silently overwrite an existing job_id
    (see https://github.com/ITISFoundation/private-issues/issues/648)."""
    comp_tasks_repo = get_repository(initialized_app, CompTasksRepository)
    task = published_project.tasks[0]
    run_id = RunID(1)
    await comp_tasks_repo.set_task_job_id(task.project_id, task.node_id, run_id, "job-id-1")
    with pytest.raises(ComputationalTaskJobIdAlreadySetError):
        await comp_tasks_repo.set_task_job_id(task.project_id, task.node_id, run_id, "job-id-2")


async def test_set_task_job_id_raises_not_found_if_task_does_not_exist(
    initialized_app: FastAPI,
    published_project: PublishedProject,
    faker: Faker,
):
    comp_tasks_repo = get_repository(initialized_app, CompTasksRepository)
    task = published_project.tasks[0]
    run_id = RunID(1)
    with pytest.raises(ComputationalTaskNotFoundError):
        await comp_tasks_repo.set_task_job_id(task.project_id, NodeID(f"{faker.uuid4()}"), run_id, "job-id-1")
