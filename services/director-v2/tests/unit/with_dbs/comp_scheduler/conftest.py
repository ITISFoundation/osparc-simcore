# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=no-value-for-parameter
# pylint:disable=protected-access
# pylint:disable=too-many-arguments
# pylint:disable=no-name-in-module
# pylint: disable=too-many-statements


from unittest import mock

import pytest
import sqlalchemy as sa
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisSettings


@pytest.fixture
def mock_env(
    mock_env: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
    fake_s3_envs: EnvVarsDict,
    postgres_db: sa.engine.Engine,
    postgres_host_config: dict[str, str],
    rabbit_service: RabbitSettings,
    redis_service: RedisSettings,
) -> EnvVarsDict:
    return mock_env | setenvs_from_dict(
        monkeypatch,
        {k: f"{v}" for k, v in fake_s3_envs.items()}
        | {
            "COMPUTATIONAL_BACKEND_ENABLED": True,
            "COMPUTATIONAL_BACKEND_DASK_CLIENT_ENABLED": True,
        },
    )


@pytest.fixture
def with_disabled_auto_scheduling(mocker: MockerFixture) -> mock.Mock:
    mocker.patch(
        "simcore_service_director_v2.modules.comp_scheduler.shutdown_manager",
    )
    return mocker.patch(
        "simcore_service_director_v2.modules.comp_scheduler.setup_manager",
    )


@pytest.fixture
def with_disabled_scheduler_worker(mocker: MockerFixture) -> mock.Mock:
    mocker.patch(
        "simcore_service_director_v2.modules.comp_scheduler.shutdown_worker",
        autospec=True,
    )
    return mocker.patch(
        "simcore_service_director_v2.modules.comp_scheduler.setup_worker",
        autospec=True,
    )


@pytest.fixture
def with_disabled_scheduler_publisher(mocker: MockerFixture) -> mock.Mock:
    return mocker.patch(
        "simcore_service_director_v2.modules.comp_scheduler._manager.request_pipeline_scheduling",
        autospec=True,
    )
