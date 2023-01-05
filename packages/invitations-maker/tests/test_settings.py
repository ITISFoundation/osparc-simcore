from invitations_maker.settings import ApplicationSettings, BasicApplicationSettings
from pytest import MonkeyPatch

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_envs import setenvs_from_dict


def test_valid_cli_application_settings(monkeypatch: MonkeyPatch, secret_key: str):
    setenvs_from_dict(
        monkeypatch,
        {
            "INVITATIONS_MAKER_SECRET_KEY": secret_key,
            "INVITATIONS_MAKER_OSPARC_URL": "https://myosparc.org",
        },
    )

    settings = BasicApplicationSettings()
    assert settings


def test_valid_web_application_settings(app_environment: EnvVarsDict):
    settings = ApplicationSettings()
    assert settings
