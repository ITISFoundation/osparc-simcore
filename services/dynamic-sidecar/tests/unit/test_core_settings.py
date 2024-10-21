# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name

import pytest
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict, setenvs_from_dict
from settings_library.utils_service import DEFAULT_AIOHTTP_PORT
from simcore_service_dynamic_sidecar.core.settings import ApplicationSettings


def test_settings_with_mock_environment(mock_environment: EnvVarsDict):
    assert ApplicationSettings.create_from_envs()


def test_settings_with_envdevel_file(mock_environment_with_envdevel: EnvVarsDict):
    assert ApplicationSettings.create_from_envs()


@pytest.fixture
def mock_postgres_data(monkeypatch: pytest.MonkeyPatch) -> None:
    setenvs_from_dict(
        monkeypatch,
        {
            "POSTGRES_HOST": "test",
            "POSTGRES_USER": "test",
            "POSTGRES_PASSWORD": "test",
            "POSTGRES_DB": "test",
        },
    )


@pytest.mark.parametrize(
    "envs",
    [
        {
            "STORAGE_USERNAME": "user",
            "STORAGE_PASSWORD": "passwd",
            "STORAGE_HOST": "host",
            "STORAGE_PORT": "42",
            "STORAGE_SECURE": "1",
        },
        {
            "NODE_PORTS_STORAGE_AUTH": (
                "{"
                '"STORAGE_USERNAME": "user", '
                '"STORAGE_PASSWORD": "passwd", '
                '"STORAGE_HOST": "host", '
                '"STORAGE_PORT": "42", '
                '"STORAGE_SECURE": "1"'
                "}"
            )
        },
    ],
)
def test_settings_with_node_ports_storage_auth(
    mock_environment: EnvVarsDict,
    mock_postgres_data: None,
    monkeypatch: pytest.MonkeyPatch,
    envs: dict[str, str],
):
    setenvs_from_dict(monkeypatch, envs)

    settings = ApplicationSettings.create_from_envs()
    assert settings.NODE_PORTS_STORAGE_AUTH
    # pylint:disable=no-member
    assert settings.NODE_PORTS_STORAGE_AUTH.STORAGE_SECURE is True
    assert settings.NODE_PORTS_STORAGE_AUTH.STORAGE_HOST == "host"
    assert settings.NODE_PORTS_STORAGE_AUTH.STORAGE_PORT == 42
    assert settings.NODE_PORTS_STORAGE_AUTH.STORAGE_USERNAME == "user"
    assert settings.NODE_PORTS_STORAGE_AUTH.auth_required is True
    assert settings.NODE_PORTS_STORAGE_AUTH.STORAGE_PASSWORD

    # enforce avoiding credentials leaks
    assert (
        settings.NODE_PORTS_STORAGE_AUTH.STORAGE_PASSWORD.get_secret_value() == "passwd"
    )
    assert "passwd" not in settings.NODE_PORTS_STORAGE_AUTH.model_dump_json()


@pytest.mark.parametrize("envs", [{}])
def test_settings_with_node_ports_storage_auth_as_missing(
    mock_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch, envs: dict[str, str]
):
    setenvs_from_dict(monkeypatch, envs)

    settings = ApplicationSettings.create_from_envs()
    assert settings.NODE_PORTS_STORAGE_AUTH is not None
    # pylint:disable=no-member
    assert settings.NODE_PORTS_STORAGE_AUTH.auth_required is False
    assert settings.NODE_PORTS_STORAGE_AUTH.STORAGE_USERNAME is None
    assert settings.NODE_PORTS_STORAGE_AUTH.STORAGE_PASSWORD is None
    assert settings.NODE_PORTS_STORAGE_AUTH.STORAGE_SECURE is False
    assert settings.NODE_PORTS_STORAGE_AUTH.STORAGE_HOST == "storage"
    assert settings.NODE_PORTS_STORAGE_AUTH.STORAGE_PORT == DEFAULT_AIOHTTP_PORT
