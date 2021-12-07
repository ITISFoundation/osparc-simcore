# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access

from typing import Any, Dict, Optional
from uuid import uuid4

import pytest
from celery.app.base import Celery
from celery.contrib.testing.worker import TestWorkController
from fastapi import FastAPI
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.settings.celery import CeleryConfig
from pydantic.types import PositiveInt
from simcore_service_director_v2.models.domains.comp_tasks import Image
from simcore_service_director_v2.models.schemas.services import NodeRequirements
from simcore_service_director_v2.modules.celery import CeleryClient

# Fixtures -----------------------------------------------------------------


@pytest.fixture
def project_id() -> ProjectID:
    return uuid4()


@pytest.fixture
def celery_configuration() -> CeleryConfig:
    return CeleryConfig.create_from_env()


@pytest.fixture
def minimal_celery_config(
    project_env_devel_environment, monkeypatch, celery_config: Dict[str, Any]
):
    """set a minimal configuration for testing the director connection only"""
    monkeypatch.setenv("DIRECTOR_V0_ENABLED", "0")
    monkeypatch.setenv("DIRECTOR_V2_POSTGRES_ENABLED", "0")
    monkeypatch.setenv("DIRECTOR_V2_CELERY_ENABLED", "1")
    monkeypatch.setenv("DIRECTOR_V2_CELERY_SCHEDULER_ENABLED", "0")
    monkeypatch.setenv("DIRECTOR_V2_DASK_CLIENT_ENABLED", "0")
    monkeypatch.setenv("DIRECTOR_V2_DASK_SCHEDULER_ENABLED", "0")

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
def test_create_task(
    minimal_celery_config: None, celery_app: Celery, celery_worker: TestWorkController
):
    @celery_app.task
    def mul(x, y):
        return x * y

    celery_worker.reload()
    assert mul.delay(4, 4).get(timeout=10) == 16


@pytest.mark.parametrize(
    "image, routing_queue",
    [
        (
            Image(
                name="simcore/services/comp/pytest",
                tag="1.2.2",
                node_requirements=NodeRequirements(CPU=1, RAM="128 MiB"),
            ),
            "cpu",
        ),
        (
            Image(
                name="simcore/services/comp/pytest",
                tag="1.2.2",
                node_requirements=NodeRequirements(CPU=1, GPU=1, RAM="256 MiB"),
            ),
            "gpu",
        ),
        (
            Image(
                name="simcore/services/comp/pytest",
                tag="1.2.2",
                node_requirements=NodeRequirements(CPU=2, RAM="128 MiB", MPI=1),
            ),
            "mpi",
        ),
    ],
)
def test_send_computation_tasks(  # pylint: disable=too-many-arguments
    minimal_celery_config,
    minimal_app: FastAPI,
    celery_app: Celery,
    celery_worker_parameters,
    celery_worker: TestWorkController,
    celery_configuration: CeleryConfig,
    user_id: PositiveInt,
    project_id: ProjectID,
    image: Image,
    routing_queue: str,
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

    celery_app.control.add_consumer(f"{celery_configuration.task_name}.{routing_queue}")
    celery_worker.reload()
    tasks: Dict[NodeID, Image] = {uuid4(): image for i in range(3)}
    celery_client: CeleryClient = minimal_app.state.celery_client
    celery_tasks = celery_client.send_computation_tasks(
        user_id, project_id, tasks, callback_fct
    )

    assert len(celery_tasks) == len(tasks)

    for node_id in tasks:
        assert node_id in celery_tasks
        task_results = celery_tasks[node_id].get(timeout=10)
        assert task_results == f"task created for {user_id} and {project_id}:{node_id}"

    callback_fct.assert_called()
