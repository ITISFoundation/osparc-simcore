# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from datetime import timedelta
from typing import Final

import pytest
from asgi_lifespan import LifespanManager
from faker import Faker
from fastapi import FastAPI
from models_library.projects import ProjectID
from pydantic import NonNegativeFloat
from pytest_mock import MockerFixture
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict, setenvs_from_dict
from simcore_service_dynamic_sidecar.core.application import create_app
from simcore_service_dynamic_sidecar.core.external_dependencies import (
    CouldNotReachExternalDependenciesError,
)
from simcore_service_dynamic_sidecar.modules.service_liveness import (
    wait_for_service_liveness as original_wait_for_service_liveness,
)

_LONG_STARTUP_SHUTDOWN_TIMEOUT: Final[NonNegativeFloat] = 60


@pytest.fixture
def mock_liveness_timeout(mocker: MockerFixture) -> None:
    # Wrap wait_for_service_liveness to inject a short timeout

    async def _wait_with_timeout(*args, **kwargs):
        # Force a short timeout for all liveness checks
        kwargs["max_delay"] = timedelta(seconds=0.5)
        kwargs["check_interval"] = timedelta(seconds=0.1)
        return await original_wait_for_service_liveness(*args, **kwargs)

    # Patch in all modules that import it
    for module in [
        "simcore_service_dynamic_sidecar.modules.database",
        "simcore_service_dynamic_sidecar.core.storage",
        "simcore_service_dynamic_sidecar.core.rabbitmq",
        "simcore_service_dynamic_sidecar.core.registry",
    ]:
        mocker.patch(
            f"{module}.wait_for_service_liveness",
            side_effect=_wait_with_timeout,
        )


@pytest.fixture
def mock_environment(
    mock_liveness_timeout: None,
    base_mock_envs: EnvVarsDict,
    project_id: ProjectID,
    monkeypatch: pytest.MonkeyPatch,
    faker: Faker,
) -> EnvVarsDict:
    return setenvs_from_dict(
        monkeypatch,
        {
            "DY_SIDECAR_CALLBACKS_MAPPING": "{}",
            "DY_SIDECAR_PROJECT_ID": f"{project_id}",
            "DY_SIDECAR_USER_ID": f"{2}",
            "DYNAMIC_SIDECAR_LOG_LEVEL": "DEBUG",
            "R_CLONE_PROVIDER": "MINIO",
            "RABBIT_HOST": "test",
            "RABBIT_PASSWORD": "test",
            "RABBIT_SECURE": "0",
            "RABBIT_USER": "test",
            "STORAGE_USERNAME": "test",
            "STORAGE_PASSWORD": "test",
            "S3_ENDPOINT": faker.url(),
            "S3_ACCESS_KEY": faker.pystr(),
            "S3_REGION": faker.pystr(),
            "S3_SECRET_KEY": faker.pystr(),
            "S3_BUCKET_NAME": faker.pystr(),
            "POSTGRES_HOST": "test",
            "POSTGRES_USER": "test",
            "POSTGRES_PASSWORD": "test",
            "POSTGRES_DB": "test",
            "REGISTRY_AUTH": f"{faker.pybool()}",
            "REGISTRY_USER": faker.user_name(),
            "REGISTRY_PW": faker.password(),
            "REGISTRY_SSL": f"{faker.pybool()}",
            "REGISTRY_URL": faker.url(),
            **base_mock_envs,
        },
    )


@pytest.fixture
async def app(mock_environment: EnvVarsDict) -> FastAPI:
    return create_app()


async def test_external_dependencies_are_not_reachable(app: FastAPI):
    with pytest.raises(CouldNotReachExternalDependenciesError) as exe_info:
        async with LifespanManager(
            app,
            startup_timeout=_LONG_STARTUP_SHUTDOWN_TIMEOUT,
            shutdown_timeout=_LONG_STARTUP_SHUTDOWN_TIMEOUT,
        ):
            ...
    failed = exe_info.value.failed
    assert len(failed) == 4

    for entry in ["Postgres", "RabbitMQ", "Internal Registry", "Storage"]:
        assert any(f"Could not contact service '{entry}'" in err for err in failed)
