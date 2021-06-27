# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from typing import Dict

import pytest
from settings_library.postgres import PostgresSettings


@pytest.fixture
def env_file():
    return ".env-granular"


def test_cached_property_dsn(mock_environment: Dict):

    settings = PostgresSettings()

    # all are upper-case
    assert all(key == key.upper() for key in settings.dict().keys())

    # dsn is computed from the other fields
    assert "dsn" not in settings.dict().keys()

    # causes cached property to be computed and stored on the instance
    assert settings.dsn

    assert "dsn" in settings.dict().keys()
