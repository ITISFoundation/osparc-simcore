# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
"""
We can validate actual .env files (also refered as `repo.config` files) by passing them via the CLI

$ ln -s /path/to/osparc-config/deployments/mydeploy.com/repo.config .secrets
$ pytest --external-envfile=.secrets --pdb tests/unit/test_core_settings.py

"""

import pytest
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_invitations.core.settings import (
    ApplicationSettings,
    MinimalApplicationSettings,
)


def test_valid_cli_application_settings(
    monkeypatch: pytest.MonkeyPatch, secret_key: str
):
    setenvs_from_dict(
        monkeypatch,
        {
            "INVITATIONS_SECRET_KEY": secret_key,
            "INVITATIONS_OSPARC_URL": "https://myosparc.org",
            "INVITATIONS_DEFAULT_PRODUCT": "s4llite",
        },
    )

    settings = MinimalApplicationSettings.create_from_envs()
    assert settings


def test_valid_application_settings(app_environment: EnvVarsDict):
    assert app_environment

    settings = ApplicationSettings()  # type: ignore
    assert settings

    assert settings == ApplicationSettings.create_from_envs()

    assert settings.INVITATIONS_LOGLEVEL == "INFO"
