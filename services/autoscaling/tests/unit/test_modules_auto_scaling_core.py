# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import logging

import pytest
from fastapi import FastAPI
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict, setenvs_from_dict
from simcore_service_autoscaling.modules.auto_scaling_core import (
    _sorted_allowed_instance_types,
)


@pytest.fixture
def with_empty_ec2_intances_allowed_types(
    monkeypatch: pytest.MonkeyPatch,
    app_environment: EnvVarsDict,
    disabled_rabbitmq: None,
    mocked_ec2_server_envs: EnvVarsDict,
    mocked_ssm_server_envs: EnvVarsDict,
    mocked_redis_server: None,
) -> EnvVarsDict:
    return app_environment | setenvs_from_dict(
        monkeypatch,
        {
            "EC2_INSTANCES_ALLOWED_TYPES": "{}",
        },
    )


async def test_sorted_allowed_instance_types__warns_with_all_available(
    with_empty_ec2_intances_allowed_types: EnvVarsDict,
    initialized_app: FastAPI,
    caplog: pytest.LogCaptureFixture,
):
    app = initialized_app

    selected_names = list(
        app.state.settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_ALLOWED_TYPES
    )
    assert not selected_names

    with caplog.at_level(logging.WARNING):
        allowed = await _sorted_allowed_instance_types(app)
        assert allowed
        assert len(allowed) > 100

    assert len(caplog.records) == 1
