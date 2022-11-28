# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from pytest_simcore.helpers.utils_envs import EnvVarsDict
from simcore_service_autoscaling.core.settings import ApplicationSettings


def test_settings(app_environment: EnvVarsDict):
    settings = ApplicationSettings.create_from_envs()
    assert settings.AUTOSCALING_EC2_ACCESS
    assert settings.AUTOSCALING_EC2_INSTANCES
    assert settings.AUTOSCALING_NODES_MONITORING
