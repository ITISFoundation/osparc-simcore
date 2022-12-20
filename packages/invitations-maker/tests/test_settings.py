from invitations_maker.settings import ApplicationSettings
from pytest import MonkeyPatch
from pytest_simcore.helpers.utils_envs import setenvs_from_dict


def test_valid_application_settings(monkeypatch: MonkeyPatch, secret_key: str):
    setenvs_from_dict(
        monkeypatch,
        {
            "INVITATIONS_MAKER_SECRET_KEY": secret_key,
            "INVITATIONS_MAKER_OSPARC_URL": "https://myosparc.org",
        },
    )

    settings = ApplicationSettings()
    assert settings
