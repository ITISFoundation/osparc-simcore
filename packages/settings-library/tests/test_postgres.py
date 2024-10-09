# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import pytest
from settings_library.postgres import PostgresSettings


@pytest.fixture
def env_file():
    return ".env-sample"


def test_cached_property_dsn(mock_environment: dict):

    settings = PostgresSettings()   # type: ignore[call-arg]

    # all are upper-case
    assert all(key == key.upper() for key in settings.model_dump())
    
    assert settings.dsn

    # dsn is computed from the other fields
    assert "dsn" not in settings.model_dump()


def test_dsn_with_query(mock_environment: dict, monkeypatch):

    settings = PostgresSettings()   # type: ignore[call-arg]

    assert not settings.POSTGRES_CLIENT_NAME
    assert settings.dsn == "postgresql://foo:secret@localhost:5432/foodb"

    # now with app
    monkeypatch.setenv("POSTGRES_CLIENT_NAME", "Some &43 funky name")

    settings_with_app = PostgresSettings()  # type: ignore[call-arg]

    assert settings_with_app.POSTGRES_CLIENT_NAME
    assert (
        settings_with_app.dsn_with_query
        == "postgresql://foo:secret@localhost:5432/foodb?application_name=Some+%2643+funky+name"
    )
