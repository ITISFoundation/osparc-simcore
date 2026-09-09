# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import pytest
from asgi_lifespan import LifespanManager
from aws_library.ec2 import SimcoreEC2API
from fastapi import FastAPI
from pytest_mock import MockerFixture
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict
from servicelib.tracing import TracingConfig
from simcore_service_clusters_keeper._meta import APP_NAME
from simcore_service_clusters_keeper.core.application import create_app
from simcore_service_clusters_keeper.core.errors import ConfigurationError
from simcore_service_clusters_keeper.core.settings import ApplicationSettings
from simcore_service_clusters_keeper.modules.ec2 import get_ec2_client
from simcore_service_clusters_keeper.modules.ssm import get_ssm_client


async def test_ec2_does_not_initialize_if_ec2_deactivated(
    disabled_rabbitmq: None,
    disabled_ec2: None,
    mocked_ssm_server_envs: EnvVarsDict,
    mocked_redis_server: None,
    initialized_app: FastAPI,
):
    assert hasattr(initialized_app.state, "ec2_client")
    assert initialized_app.state.ec2_client is None
    with pytest.raises(ConfigurationError):
        get_ec2_client(initialized_app)

    assert get_ssm_client(initialized_app)


async def test_ec2_client_is_closed_if_instrumentation_wiring_fails(
    disabled_rabbitmq: None,
    mocked_ec2_server_envs: EnvVarsDict,
    mocked_primary_ec2_instances_envs: EnvVarsDict,
    mocked_ssm_server_envs: EnvVarsDict,
    mocked_redis_server: None,
    app_environment: EnvVarsDict,
    mocker: MockerFixture,
):
    # the ec2 client is created successfully (holding real resources) but wiring
    # instrumentation onto it fails afterwards: it must still be closed, not leaked
    close_spy = mocker.patch.object(SimcoreEC2API, "close", autospec=True)
    mocker.patch(
        "aws_library.ec2._instrumentation.instrument_ec2_client",
        side_effect=RuntimeError("boom"),
    )

    settings = ApplicationSettings.create_from_envs()
    tracing_config = TracingConfig.create(service_name=APP_NAME, tracing_settings=None)
    app = create_app(settings, tracing_config=tracing_config)

    with pytest.raises(RuntimeError, match="boom"):
        async with LifespanManager(app, startup_timeout=10, shutdown_timeout=10):
            pytest.fail("lifespan startup should fail before entering the context")

    close_spy.assert_called_once()
