# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from typing import Dict

import pytest
from settings_library.postgres import PostgresSettings


@pytest.fixture
def env_file():
    return ".env-sample"


def test_cached_property_dsn(mock_environment: Dict):

    settings = PostgresSettings()

    # all are upper-case
    assert all(key == key.upper() for key in settings.dict().keys())

    # dsn is computed from the other fields
    assert "dsn" not in settings.dict().keys()

    # causes cached property to be computed and stored on the instance
    assert settings.dsn

    assert "dsn" in settings.dict().keys()


def test_dsn_with_query(mock_environment: Dict, monkeypatch):

    settings = PostgresSettings()

    assert not settings.POSTGRES_CLIENT_NAME
    assert settings.dsn == "postgresql://foo:secret@localhost:5432/foodb"

    # now with app
    monkeypatch.setenv("POSTGRES_CLIENT_NAME", "Some &43 funky name")

    settings_with_app = PostgresSettings()

    assert settings_with_app.POSTGRES_CLIENT_NAME
    assert (
        settings_with_app.dsn_with_query
        == "postgresql://foo:secret@localhost:5432/foodb?application_name=Some+%2643+funky+name"
    )
