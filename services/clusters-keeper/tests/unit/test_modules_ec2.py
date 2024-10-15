# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import pytest
from fastapi import FastAPI
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict
from simcore_service_clusters_keeper.core.errors import ConfigurationError
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
