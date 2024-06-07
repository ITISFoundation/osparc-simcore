# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from fastapi import FastAPI
from pytest_simcore.helpers.utils_envs import EnvVarsDict
from simcore_service_autoscaling.modules.auto_scaling_mode_dynamic import (
    DynamicAutoscaling,
)
from simcore_service_autoscaling.modules.buffer_machine_core import (
    monitor_buffer_machines,
)


async def test_monitor_buffer_machines(
    disabled_rabbitmq: None,
    mocked_ec2_server_envs: EnvVarsDict,
    mocked_redis_server: None,
    enabled_dynamic_mode: EnvVarsDict,
    initialized_app: FastAPI,
):
    await monitor_buffer_machines(
        initialized_app, auto_scaling_mode=DynamicAutoscaling()
    )
