# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import pytest
from fastapi import FastAPI
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_envs import setenvs_from_dict


@pytest.fixture
def app_environment(
    app_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch
) -> EnvVarsDict:
    return app_environment | setenvs_from_dict(
        monkeypatch,
        envs={
            "SC_BOOT_MODE": "debug-ptvsd",
        },
    )


def test_application_with_debug_enabled(
    disabled_rabbitmq: None,
    disabled_ec2: None,
    mocked_redis_server: None,
    initialized_app: FastAPI,
):
    ...
