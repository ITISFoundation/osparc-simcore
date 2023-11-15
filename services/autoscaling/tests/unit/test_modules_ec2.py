# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import pytest
from fastapi import FastAPI
from simcore_service_autoscaling.core.errors import ConfigurationError
from simcore_service_autoscaling.modules.ec2 import get_ec2_client


async def test_ec2_does_not_initialize_if_deactivated(
    disabled_rabbitmq: None,
    disabled_ec2: None,
    mocked_redis_server: None,
    initialized_app: FastAPI,
):
    assert hasattr(initialized_app.state, "ec2_client")
    assert initialized_app.state.ec2_client is None
    with pytest.raises(ConfigurationError):
        get_ec2_client(initialized_app)
