import pytest
from fastapi import FastAPI
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_autoscaling.core.errors import ConfigurationError
from simcore_service_autoscaling.modules.instrumentation._core import (
    get_instrumentation,
    has_instrumentation,
)


@pytest.fixture
def disabled_instrumentation(
    app_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AUTOSCALING_PROMETHEUS_INSTRUMENTATION_ENABLED", "false")


async def test_disabled_instrumentation(
    disabled_rabbitmq: None,
    disabled_ec2: None,
    disabled_ssm: None,
    disabled_instrumentation: None,
    mocked_redis_server: None,
    initialized_app: FastAPI,
):
    # instrumentation disabled by default
    assert not has_instrumentation(initialized_app)

    with pytest.raises(ConfigurationError):
        get_instrumentation(initialized_app)
