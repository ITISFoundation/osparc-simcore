# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import pytest
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_envs import setenvs_from_dict
from simcore_service_payments.core.settings import ApplicationSettings


def test_valid_cli_application_settings(
    monkeypatch: pytest.MonkeyPatch, secret_key: str
):
    setenvs_from_dict(
        monkeypatch,
        {
            "INVITATIONS_SECRET_KEY": secret_key,
            "INVITATIONS_OSPARC_URL": "https://myosparc.org",
        },
    )

    settings = MinimalApplicationSettings()
    assert settings


def test_valid_web_application_settings(app_environment: EnvVarsDict):
    settings = ApplicationSettings()
    assert settings
