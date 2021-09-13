# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=no-value-for-parameter


from typing import Dict, Iterator

import aiopg
import pytest
from _pytest.monkeypatch import MonkeyPatch
from fastapi.applications import FastAPI
from models_library.settings.rabbit import RabbitConfig
from models_library.settings.redis import RedisConfig
from simcore_service_director_v2.core.application import init_app
from simcore_service_director_v2.core.errors import ConfigurationError
from simcore_service_director_v2.core.settings import AppSettings
from starlette.testclient import TestClient

pytest_simcore_core_services_selection = ["postgres", "redis", "rabbit"]
pytest_simcore_ops_services_selection = ["adminer", "redis-commander"]


@pytest.fixture
def minimal_celery_scheduler_config(
    mock_env: None,
    postgres_host_config: Dict[str, str],
    redis_service: RedisConfig,
    rabbit_service: RabbitConfig,
    monkeypatch: MonkeyPatch,
) -> None:
    """set a minimal configuration for testing the dask connection only"""
    monkeypatch.setenv("DIRECTOR_V2_DYNAMIC_SIDECAR_ENABLED", "false")
    monkeypatch.setenv("DIRECTOR_V0_ENABLED", "0")
    monkeypatch.setenv("DIRECTOR_V2_POSTGRES_ENABLED", "1")
    monkeypatch.setenv("DIRECTOR_V2_CELERY_ENABLED", "1")
    monkeypatch.setenv("DIRECTOR_V2_CELERY_SCHEDULER_ENABLED", "1")
    monkeypatch.setenv("DIRECTOR_V2_DASK_CLIENT_ENABLED", "0")
    monkeypatch.setenv("DIRECTOR_V2_DASK_SCHEDULER_ENABLED", "0")


def test_scheduler_gracefully_starts_and_stops(
    minimal_celery_scheduler_config: None,
    aiopg_engine: Iterator[aiopg.sa.engine.Engine],  # type: ignore
    minimal_app: FastAPI,
):
    assert minimal_app.state.scheduler_task is not None


@pytest.mark.parametrize(
    "missing_dependency",
    [
        "DIRECTOR_V2_POSTGRES_ENABLED",
        "DIRECTOR_V2_CELERY_ENABLED",
    ],
)
def test_scheduler_raises_exception_for_missing_dependencies(
    minimal_celery_scheduler_config: None,
    aiopg_engine: Iterator[aiopg.sa.engine.Engine],  # type: ignore
    monkeypatch: MonkeyPatch,
    missing_dependency: str,
):
    # disable the dependency
    monkeypatch.setenv(missing_dependency, "0")
    # create the client
    settings = AppSettings.create_from_envs()
    app = init_app(settings)

    with pytest.raises(ConfigurationError):
        with TestClient(app, raise_server_exceptions=True) as _:
            pass
