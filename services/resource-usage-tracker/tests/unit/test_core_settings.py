# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_resource_usage_tracker.core.settings import (
    ApplicationSettings,
    MinimalApplicationSettings,
)


def test_valid_cli_application_settings(app_environment: EnvVarsDict):
    settings = MinimalApplicationSettings.create_from_envs()
    assert settings
    assert settings.RESOURCE_USAGE_TRACKER_PROMETHEUS
    assert settings.RESOURCE_USAGE_TRACKER_POSTGRES
    assert settings.RESOURCE_USAGE_TRACKER_REDIS
    assert settings.RESOURCE_USAGE_TRACKER_RABBITMQ
    assert settings.LOG_LEVEL


def test_valid_web_application_settings(app_environment: EnvVarsDict):
    settings = ApplicationSettings.create_from_envs()
    assert settings
    assert settings.RESOURCE_USAGE_TRACKER_PROMETHEUS
    assert settings.RESOURCE_USAGE_TRACKER_POSTGRES
    assert settings.RESOURCE_USAGE_TRACKER_REDIS
    assert settings.RESOURCE_USAGE_TRACKER_RABBITMQ
    assert settings.LOG_LEVEL
