# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name

import pytest
from pytest_simcore.helpers.utils_envs import EnvVarsDict, setenvs_from_dict
from simcore_service_dynamic_sidecar.core.settings import ApplicationSettings


def test_settings_with_mock_environment(mock_environment: EnvVarsDict):
    assert ApplicationSettings.create_from_envs()


def test_settings_with_envdevel_file(mock_environment_with_envdevel: EnvVarsDict):
    assert ApplicationSettings.create_from_envs()


@pytest.mark.parametrize(
    "envs",
    [
        {
            "STORAGE_LOGIN": "login",
            "STORAGE_PASSWORD": "passwd",
            "STORAGE_HOST": "host",
            "STORAGE_PORT": "42",
        },
        {
            "NODE_PORTS_STORAGE_AUTH": (
                '{"STORAGE_LOGIN": "login", '
                '"STORAGE_PASSWORD": "passwd", '
                '"STORAGE_HOST": "host", '
                '"STORAGE_PORT": "42"}'
            )
        },
    ],
)
def test_settings_with_node_ports_storage_auth(
    mock_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch, envs: dict[str, str]
):
    setenvs_from_dict(monkeypatch, envs)

    settings = ApplicationSettings.create_from_envs()
    assert settings.NODE_PORTS_STORAGE_AUTH is not None
    assert settings.NODE_PORTS_STORAGE_AUTH.STORAGE_HOST == "host"
    assert settings.NODE_PORTS_STORAGE_AUTH.STORAGE_PORT == 42
    assert settings.NODE_PORTS_STORAGE_AUTH.STORAGE_LOGIN == "login"
    assert (
        settings.NODE_PORTS_STORAGE_AUTH.STORAGE_PASSWORD.get_secret_value() == "passwd"
    )
    # json serializes password to plain text
    assert "passwd" not in settings.NODE_PORTS_STORAGE_AUTH.json()
    assert "passwd" in settings.NODE_PORTS_STORAGE_AUTH.unsafe_json()


@pytest.mark.parametrize(
    "envs",
    [
        {},
        {"NODE_PORTS_STORAGE_AUTH": "null"},
    ],
)
def test_settings_with_node_ports_storage_auth_as_missing(
    mock_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch, envs: dict[str, str]
):
    setenvs_from_dict(monkeypatch, envs)

    settings = ApplicationSettings.create_from_envs()
    assert settings.NODE_PORTS_STORAGE_AUTH is None
