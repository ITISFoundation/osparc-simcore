# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from pytest import MonkeyPatch
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_envs import setenvs_from_dict
from simcore_service_resource_usage.core.settings import (
    ApplicationSettings,
    MinimalApplicationSettings,
)


def test_valid_cli_application_settings(
    monkeypatch: MonkeyPatch,
    fake_user_name: str,
    fake_port: int,
    fake_url: str,
    fake_password: str,
):
    setenvs_from_dict(
        monkeypatch,
        {
            "RESOURCE_USAGE_PROMETHEUS_PASSWORD": fake_password,
            "RESOURCE_USAGE_PROMETHEUS_PORT": str(fake_port),
            "RESOURCE_USAGE_PROMETHEUS_USERNAME": fake_user_name,
            "RESOURCE_USAGE_PROMETHEUS_URL": fake_url,
        },
    )

    settings = MinimalApplicationSettings()
    assert settings


def test_valid_web_application_settings(app_environment: EnvVarsDict):
    settings = ApplicationSettings()
    assert settings
