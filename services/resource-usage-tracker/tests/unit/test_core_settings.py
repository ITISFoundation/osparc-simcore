# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
"""
We can validate actual .env files (also refered as `repo.config` files) by passing them via the CLI

$ ln -s /path/to/osparc-config/deployments/mydeploy.com/repo.config .secrets
$ pytest --external-envfile=.secrets --pdb tests/unit/test_core_settings.py

"""

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
    assert settings.RESOURCE_USAGE_TRACKER_LOGLEVEL


def test_valid_web_application_settings(app_environment: EnvVarsDict):
    settings = ApplicationSettings.create_from_envs()
    assert settings
    assert settings.RESOURCE_USAGE_TRACKER_PROMETHEUS
    assert settings.RESOURCE_USAGE_TRACKER_POSTGRES
    assert settings.RESOURCE_USAGE_TRACKER_REDIS
    assert settings.RESOURCE_USAGE_TRACKER_RABBITMQ
    assert settings.RESOURCE_USAGE_TRACKER_LOGLEVEL
