# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=protected-access


import pytest
from fastapi import FastAPI
from simcore_service_autoscaling.core.errors import ConfigurationError
from simcore_service_autoscaling.modules.ssm import get_ssm_client


async def test_ssm_does_not_initialize_if_deactivated(
    disabled_rabbitmq: None,
    disabled_ec2: None,
    disabled_ssm: None,
    mocked_redis_server: None,
    initialized_app: FastAPI,
):
    assert hasattr(initialized_app.state, "ssm_client")
    assert initialized_app.state.ssm_client is None
    with pytest.raises(ConfigurationError):
        get_ssm_client(initialized_app)
