# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access

from random import randint
from time import sleep, time
from typing import Optional
from uuid import uuid4

import pytest
from celery.contrib.abortable import AbortableTask
from fastapi import FastAPI
from models_library.settings.celery import CeleryConfig
from pydantic.types import PositiveInt
from simcore_service_director_v2.modules.celery import CeleryClient


@pytest.fixture
def user_id() -> PositiveInt:
    return randint(0, 10000)


@pytest.fixture
def project_id() -> str:
    return str(uuid4())


# PYTEST-CELERY Fixtures -----------------------------------------------------------------
BROKER = "memory://"
RESULT_BACKEND = "rpc://"


@pytest.fixture(scope="session")
def celery_config():
    # NOTE: forces celery to use in-memory broker
    return {"broker_url": BROKER, "result_backend": RESULT_BACKEND}


@pytest.fixture(scope="session")
def celery_enable_logging():
    return True


# test pytest-celery here
# https://github.com/celery/celery/issues/3642#issuecomment-369057682 defines why this works
def test_create_task(celery_app, celery_worker):
    @celery_app.task
    def mul(x, y):
        return x * y

    celery_worker.reload()
    assert mul.delay(4, 4).get(timeout=10) == 16


@pytest.fixture
def celery_configuration() -> CeleryConfig:
    return CeleryConfig.create_from_env()


@pytest.fixture(autouse=True)
def minimal_celery_config(monkeypatch):
    """set a minimal configuration for testing the director connection only"""
    monkeypatch.setenv("DIRECTOR_ENABLED", "0")
    monkeypatch.setenv("POSTGRES_ENABLED", "0")
    monkeypatch.setenv("CELERY_ENABLED", "1")
    monkeypatch.setenv("REGISTRY_ENABLED", "0")

    monkeypatch.setattr(CeleryConfig, "broker_url", BROKER)
    monkeypatch.setattr(CeleryConfig, "result_backend", RESULT_BACKEND)


def test_celery_configuration(
    minimal_celery_config, celery_configuration: CeleryConfig
):
    assert celery_configuration.broker_url == BROKER
    assert celery_configuration.result_backend == RESULT_BACKEND


def test_send_tasks(minimal_app: FastAPI, celery_app, celery_worker):
    @celery_app.task(name="some_task")
    def some_task(x, y):
        return x * y

    celery_worker.reload()

    celery_client: CeleryClient = minimal_app.state.celery_client
    task = celery_client.send_task("some_task", args=[2, 3])
    assert task.get(timeout=10) == 6


def test_send_computation_task(
    minimal_app: FastAPI,
    celery_app,
    celery_worker,
    celery_configuration,
    user_id,
    project_id,
):
    @celery_app.task(name=celery_configuration.task_name)
    def some_task(
        *, user_id: int, project_id: str, node_id: Optional[str] = None
    ) -> str:
        return f"task created for {user_id} and {project_id}:{node_id}"

    celery_worker.reload()

    celery_client: CeleryClient = minimal_app.state.celery_client
    task = celery_client.send_computation_task(user_id, project_id)
    assert task.get(timeout=10) == f"task created for {user_id} and {project_id}:None"


@pytest.mark.skip("unable to make that work in a unit test")
def test_aborting_task(
    minimal_app: FastAPI,
    celery_app,
    celery_worker,
    celery_configuration,
    user_id,
    project_id,
):
    # now create a sleeping task that we can abort
    @celery_app.task(name=celery_configuration.task_name, base=AbortableTask, bind=True)
    def a_sleeping_task(
        self, *, user_id: int, project_id: str, node_id: Optional[str] = None
    ) -> str:
        now = time()
        while time() - now < 10:
            print("hello!")
            if self.is_aborted():
                return f"task created for {user_id} and {project_id}:{node_id}"
            sleep(1)
        assert False

    celery_worker.reload()

    celery_client: CeleryClient = minimal_app.state.celery_client
    task = celery_client.send_computation_task(user_id, project_id)
