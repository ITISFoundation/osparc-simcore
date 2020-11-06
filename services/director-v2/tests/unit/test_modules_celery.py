import pytest
from fastapi import FastAPI
from simcore_service_director_v2.modules.celery import CeleryClient


@pytest.fixture(scope="session")
def celery_config():
    # NOTE: forces celery to use in-memory broker
    return {"broker_url": "memory://", "result_backend": "rpc"}


# test pytest-celery here
# https://github.com/celery/celery/issues/3642#issuecomment-369057682 defines why this works
def test_create_task(celery_app, celery_worker):
    @celery_app.task
    def mul(x, y):
        return x * y

    celery_worker.reload()
    assert mul.delay(4, 4).get(timeout=10) == 16


@pytest.fixture(autouse=True)
def minimal_celery_config(monkeypatch):
    """set a minimal configuration for testing the director connection only"""
    monkeypatch.setenv("DIRECTOR_ENABLED", "0")
    monkeypatch.setenv("POSTGRES_ENABLED", "0")
    monkeypatch.setenv("CELERY_ENABLED", "1")
    monkeypatch.setenv("REGISTRY_ENABLED", "0")


def test_send_tasks(minimal_app: FastAPI):
    celery_client: CeleryClient = minimal_app.state.celery_client
    task = celery_client.send_task("some_name")
    assert task
    assert False
