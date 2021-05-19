# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access

from random import randint, random
from typing import Any, Dict, List, Optional
from uuid import uuid4

import pytest
from celery.app.base import Celery
from celery.contrib.testing.worker import TestWorkController
from fastapi import FastAPI
from models_library.settings.celery import CeleryConfig
from pydantic.types import PositiveInt
from simcore_service_director_v2.modules.celery import CeleryClient


# Fixtures -----------------------------------------------------------------
@pytest.fixture
def user_id() -> PositiveInt:
    return randint(0, 10000)


@pytest.fixture
def project_id() -> str:
    return str(uuid4())


@pytest.fixture
def celery_configuration() -> CeleryConfig:
    return CeleryConfig.create_from_env()


@pytest.fixture(autouse=True)
def minimal_celery_config(
    project_env_devel_environment, monkeypatch, celery_config: Dict[str, Any]
):
    """set a minimal configuration for testing the director connection only"""
    monkeypatch.setenv("DIRECTOR_ENABLED", "0")
    monkeypatch.setenv("POSTGRES_ENABLED", "0")
    monkeypatch.setenv("CELERY_ENABLED", "1")
    monkeypatch.setenv("REGISTRY_ENABLED", "0")
    monkeypatch.setenv("DIRECTOR_V2_SCHEDULER_ENABLED", "0")

    monkeypatch.setattr(CeleryConfig, "broker_url", celery_config["broker_url"])
    monkeypatch.setattr(CeleryConfig, "result_backend", celery_config["result_backend"])


# PYTEST-CELERY special Fixtures -----------------------------------------------------------------


@pytest.fixture(scope="session")
def celery_config() -> Dict[str, Any]:
    # NOTE: forces celery to use in-memory broker
    return {
        "broker_url": "memory://",
        "result_backend": "cache",
        "cache_backend": "memory",
    }


@pytest.fixture(scope="session")
def celery_worker_parameters():
    return {
        "queues": ("celery"),
    }


@pytest.fixture(scope="session")
def celery_enable_logging() -> bool:
    # This is a fixture you can override to enable logging in embedded workers.
    return True


# test pytest-celery here
# https://github.com/celery/celery/issues/3642#issuecomment-369057682 defines why this works
def test_create_task(celery_app: Celery, celery_worker: TestWorkController):
    @celery_app.task
    def mul(x, y):
        return x * y

    celery_worker.reload()
    assert mul.delay(4, 4).get(timeout=10) == 16


def sorted_nodes() -> List[Dict[str, Dict[str, Any]]]:
    possible_requirements
    return [
        {
            "grp_1_node_0": {"runtime_requirements": "cpu"},
            "grp_1_node_1": {"runtime_requirements": "cpu"},
        },
        {
            "grp_2_node_0": {"runtime_requirements": "cpu"},
            "grp_2_node_1": {"runtime_requirements": "cpu"},
        },
        {
            "grp_3_node_0": {"runtime_requirements": "cpu"},
            "grp_3_node_1": {"runtime_requirements": "cpu"},
        },
        {
            "grp_4_node_0": {"runtime_requirements": "cpu"},
            "grp_4_node_1": {"runtime_requirements": "cpu"},
        },
    ]


@pytest.mark.parametrize("runtime_requirements", ["cpu", "gpu", "mpi", "gpu/mpi"])
def test_send_single_tasks(
    minimal_app: FastAPI,
    celery_app: Celery,
    celery_worker_parameters: None,
    celery_worker: TestWorkController,
    celery_configuration: CeleryConfig,
    user_id: PositiveInt,
    project_id: str,
    runtime_requirements: str,
    mocker,
):
    callback_fct = mocker.MagicMock()

    @celery_app.task(name=celery_configuration.task_name, bind=True)
    def some_task(
        self,
        *args,
        user_id: int,
        project_id: str,
        node_id: Optional[str] = None,
        **kwargs,
    ) -> str:
        return f"task created for {user_id} and {project_id}:{node_id}"

    celery_app.control.add_consumer(
        f"{celery_configuration.task_name}.{runtime_requirements}"
    )
    celery_worker.reload()

    list_of_tasks = {
        f"task_{i}": {"runtime_requirements": runtime_requirements} for i in range(3)
    }
    celery_client: CeleryClient = minimal_app.state.celery_client
    celery_tasks = celery_client.send_single_tasks(
        user_id, project_id, list_of_tasks, callback_fct
    )

    assert len(celery_tasks) == len(list_of_tasks)

    for task_id, task_data in celery_tasks.items():
        assert task_id in list_of_tasks
        list_of_tasks.pop(task_id)
        task_results = task_data.get(timeout=10)
        assert task_results == f"task created for {user_id} and {project_id}:{task_id}"
    callback_fct.assert_called()
