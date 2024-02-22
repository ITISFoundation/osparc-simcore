# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name

import pytest
from pytest_simcore.helpers.utils_envs import EnvVarsDict, setenvs_from_dict
from simcore_service_dynamic_sidecar.core.settings import ApplicationSettings


def test_settings_with_mock_environment(mock_environment: EnvVarsDict):
    assert ApplicationSettings.create_from_envs()


def test_settings_with_envdevel_file(mock_environment_with_envdevel: EnvVarsDict):
    settings = ApplicationSettings.create_from_envs()
    assert settings
    assert settings.NODE_PORTS_STORAGE_AUTH is None


@pytest.mark.parametrize(
    "envs",
    [
        {
            "NODE_PORTS_STORAGE_LOGIN": "login",
            "NODE_PORTS_STORAGE_PASSWORD": "passwd",
        },
        {
            "NODE_PORTS_STORAGE_AUTH": '{"NODE_PORTS_STORAGE_LOGIN": "login", "NODE_PORTS_STORAGE_PASSWORD": "passwd"}'
        },
    ],
)
def test_settings_with_node_ports_storage_auth(
    mock_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch, envs: dict[str, str]
):
    setenvs_from_dict(monkeypatch, envs)

    settings = ApplicationSettings.create_from_envs()
    assert settings.NODE_PORTS_STORAGE_AUTH is not None
    assert settings.NODE_PORTS_STORAGE_AUTH.NODE_PORTS_STORAGE_LOGIN == "login"
    assert (
        settings.NODE_PORTS_STORAGE_AUTH.NODE_PORTS_STORAGE_PASSWORD.get_secret_value()
        == "passwd"
    )
    # json serializes password to plain text
    assert "passwd" in settings.NODE_PORTS_STORAGE_AUTH.json()
