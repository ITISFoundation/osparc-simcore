# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from io import StringIO
from typing import Optional

import pytest
from dotenv import dotenv_values
from pydantic import Field, ValidationError
from settings_library.base import AUTO_DEFAULT_FROM_ENV_VARS, BaseCustomSettings
from settings_library.postgres import PostgresSettings

# HELPERS --------------------------------------------------------------------------------


class _SimplePostgresSettings(PostgresSettings):
    POSTGRES_PASSWORD: str


# FIXTURES --------------------------------------------------------------------------------
#
#
# NOTE: Pydantic models are returned by function-scoped fixture such that every
#       test starts with a fresh Model class (notice that pydanctic classes involve meta-operations
#       that modify the definition of class models upon import).
#
#
# NOTE: all int defaults are 42, i.e. the "Answer to the Ultimate Question of Life, the Universe, and Everything"
#
# NOTE: suffixes are used to distinguis different options on the same field (e.g. _OPTIONAL, etc)
#


@pytest.fixture
def fake_settings_class():
    # NOTE: that this class inherits from BaseSettings
    # Typically used to capture env vars for a shared module (e.g. postgres) and
    # embed them in a general settings
    class _Settings(BaseCustomSettings):
        SETTINGS_VALUE: int
        SETTINGS_VALUE_DEFAULT: int = 42
        SETTINGS_VALUE_OPTIONAL: Optional[int]
        SETTINGS_VALUE_OPTIONAL_DEFAULT_VALUE: Optional[int] = 42
        SETTINGS_VALUE_OPTIONAL_DEFAULT_NONE: Optional[int] = None

    return _Settings


@pytest.fixture
def fake_main_settings_with_postgres():
    class _MainSettingsVariants:
        #
        # Different constraints on WEBSERVER_POSTGRES subsettings
        #
        class AsRequired(BaseCustomSettings):
            # required
            WEBSERVER_POSTGRES: _SimplePostgresSettings

        class AsOptionalUndefined(BaseCustomSettings):
            # optional with undefined default
            WEBSERVER_POSTGRES: Optional[_SimplePostgresSettings]

        class AsOptionalAutoDefault(BaseCustomSettings):
            # optional with auto default i.e. delayed default factory
            WEBSERVER_POSTGRES: _SimplePostgresSettings = Field(
                AUTO_DEFAULT_FROM_ENV_VARS
            )

        class AsNullableAutoDefault(BaseCustomSettings):
            # optional, nullable and with auto default (= enabled by default)
            WEBSERVER_POSTGRES: Optional[_SimplePostgresSettings] = Field(
                AUTO_DEFAULT_FROM_ENV_VARS
            )

        class AsDefaultNone(BaseCustomSettings):
            # optional, nullable and None default (= disabled by default)
            WEBSERVER_POSTGRES: Optional[_SimplePostgresSettings] = None

    return _MainSettingsVariants


# TESTS -----------------------------------------------------------------------------------------------------
#
# NOTE: Tests below are progressive to understand and validate the construction mechanism
#       implemented in BaseCustomSettings.
#       Pay attention how the defaults of SubSettings are automaticaly captured from env vars
#       at construction time.
#


def test_create_settings_from_env(monkeypatch, fake_settings_class):
    # NOTE : we use this test to check how it behaves with an int
    #        and expect the same behaviour later with PostgresSettings

    _Settings = fake_settings_class

    # environ 1
    monkeypatch.setenv("SETTINGS_VALUE", 1)

    settings = _Settings.create_from_envs()

    assert settings.dict() == {
        "SETTINGS_VALUE": 1,
        "SETTINGS_VALUE_DEFAULT": 42,
        "SETTINGS_VALUE_OPTIONAL": None,
        "SETTINGS_VALUE_OPTIONAL_DEFAULT_VALUE": 42,
        "SETTINGS_VALUE_OPTIONAL_DEFAULT_NONE": None,
    }
    assert settings.dict(exclude_unset=True) == {
        "SETTINGS_VALUE": 1,
    }

    # environ 2
    monkeypatch.setenv("SETTINGS_VALUE_OPTIONAL_DEFAULT_NONE", 2)

    settings = _Settings.create_from_envs()

    assert settings.dict(exclude_unset=True) == {
        "SETTINGS_VALUE": 1,
        "SETTINGS_VALUE_OPTIONAL_DEFAULT_NONE": 2,
    }

    # environ 3
    monkeypatch.setenv("SETTINGS_VALUE_OPTIONAL_DEFAULT_NONE", 2)

    settings = _Settings.create_from_envs()

    assert settings.dict(exclude_unset=True) == {
        "SETTINGS_VALUE": 1,
        "SETTINGS_VALUE_OPTIONAL_DEFAULT_NONE": 2,
    }


def test_create_settings_from_env_1(monkeypatch, fake_main_settings_with_postgres):

    _MainSettings = fake_main_settings_with_postgres

    with pytest.raises(ValidationError):
        s1 = _MainSettings.AsRequired.create_from_envs()

    s2 = _MainSettings.AsOptionalUndefined.create_from_envs()
    assert s2.dict() == {"WEBSERVER_POSTGRES": None}

    with pytest.raises(ValidationError):
        # raises auto-default factory
        s3 = _MainSettings.AsOptionalAutoDefault.create_from_envs()

    with pytest.raises(ValidationError):
        # cannot build default
        s4 = _MainSettings.AsNullableAutoDefault.create_from_envs()

    s5 = _MainSettings.AsDefaultNone.create_from_envs()
    assert s5.dict() == {"WEBSERVER_POSTGRES": None}


def test_create_settings_from_env_2(monkeypatch, fake_main_settings_with_postgres):

    _MainSettings = fake_main_settings_with_postgres

    # environments with individual envs (PostgresSettings required fields)
    envs = dotenv_values(
        stream=StringIO(
            """
            POSTGRES_HOST=pg
            POSTGRES_USER=test
            POSTGRES_PASSWORD=shh
            POSTGRES_DB=db
        """
        ),
    )
    for key, value in envs.items():
        monkeypatch.setenv(key, str(value))

    # WEBSERVER_POSTGRES should be

    # checks
    s1 = _MainSettings.AsRequired.create_from_envs()

    assert s1.dict(exclude_unset=True) == {
        "WEBSERVER_POSTGRES": {
            "POSTGRES_HOST": "pg",
            "POSTGRES_USER": "test",
            "POSTGRES_PASSWORD": "shh",
            "POSTGRES_DB": "db",
        }
    }

    s2 = _MainSettings.AsOptionalUndefined.create_from_envs()

    assert s2.dict(exclude_unset=True) == {
        "WEBSERVER_POSTGRES": {
            "POSTGRES_HOST": "pg",
            "POSTGRES_USER": "test",
            "POSTGRES_PASSWORD": "shh",
            "POSTGRES_DB": "db",
        }
    }

    s3 = _MainSettings.AsOptionalAutoDefault.create_from_envs()

    assert s3.dict(exclude_unset=True) == {}
    assert s3.dict() == {
        "WEBSERVER_POSTGRES": {
            "POSTGRES_HOST": "pg",
            "POSTGRES_USER": "test",
            "POSTGRES_PASSWORD": "shh",
            "POSTGRES_DB": "db",
        }
    }

    s4 = _MainSettings.AsNullableAutoDefault.create_from_envs()
    assert s4.dict(exclude_unset=True) == {}
    assert s4.dict() == {
        "WEBSERVER_POSTGRES": {
            "POSTGRES_HOST": "pg",
            "POSTGRES_USER": "test",
            "POSTGRES_PASSWORD": "shh",
            "POSTGRES_DB": "db",
        }
    }

    s5 = _MainSettings.AsDefaultNone.create_from_envs()
    assert s5.dict(exclude_unset=True) == {
        "WEBSERVER_POSTGRES": {
            "POSTGRES_HOST": "pg",
            "POSTGRES_USER": "test",
            "POSTGRES_PASSWORD": "shh",
            "POSTGRES_DB": "db",
        }
    }


def test_create_settings_from_env_3(monkeypatch, fake_main_settings_with_postgres):

    _MainSettings = fake_main_settings_with_postgres

    # environment with json (compact)
    envs = dotenv_values(
        stream=StringIO(
            """
            WEBSERVER_POSTGRES='{"POSTGRES_HOST":"pg2", "POSTGRES_USER":"test2", "POSTGRES_PASSWORD":"shh2", "POSTGRES_DB":"db2"}'
        """
        )
    )

    # test
    s1 = _MainSettings.AsRequired.create_from_envs()
    s2 = _MainSettings.AsOptionalUndefined.create_from_envs()
    s3 = _MainSettings.AsOptionalAutoDefault.create_from_envs()
    s4 = _MainSettings.AsNullableAutoDefault.create_from_envs()
    s5 = _MainSettings.AsDefaultNone.create_from_envs()
