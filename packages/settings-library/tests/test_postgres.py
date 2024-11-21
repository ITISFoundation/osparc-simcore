# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from urllib.parse import urlparse

import pytest
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from settings_library.postgres import PostgresSettings


@pytest.fixture
def env_file():
    return ".env-sample"


@pytest.fixture
def mock_environment(mock_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch):
    return mock_environment | setenvs_from_dict(
        monkeypatch, {"POSTGRES_CLIENT_NAME": "Some &43 funky name"}
    )


def test_cached_property_dsn(mock_environment: EnvVarsDict):

    settings = PostgresSettings.create_from_envs()

    # all are upper-case
    assert all(key == key.upper() for key in settings.model_dump())

    assert settings.dsn

    # dsn is computed from the other fields
    assert "dsn" not in settings.model_dump()


def test_dsn_with_query(mock_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch):
    settings = PostgresSettings()

    assert settings.POSTGRES_CLIENT_NAME
    assert settings.dsn == "postgresql://foo:secret@localhost:5432/foodb"
    assert (
        settings.dsn_with_query
        == "postgresql://foo:secret@localhost:5432/foodb?application_name=Some+%2643+funky+name"
    )

    with monkeypatch.context() as patch:
        patch.delenv("POSTGRES_CLIENT_NAME")
        settings = PostgresSettings()

        assert not settings.POSTGRES_CLIENT_NAME
        assert settings.dsn == settings.dsn_with_query


def test_dsn_with_async_sqlalchemy_has_query(
    mock_environment: EnvVarsDict, monkeypatch
):
    settings = PostgresSettings()

    parsed_url = urlparse(settings.dsn_with_async_sqlalchemy)
    assert parsed_url.scheme.split("+") == ["postgresql", "asyncpg"]

    assert not parsed_url.query
