# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from io import StringIO
from typing import Optional

import pytest
from dotenv import dotenv_values
from pydantic import Field, ValidationError
from pytest_simcore.helpers.typing_env import EnvVarsDict
from settings_library.base import (
    AUTO_DEFAULT_FROM_ENV_VARS,
    AutoDefaultFactoryError,
    BaseCustomSettings,
)
from settings_library.basic_types import PortInt

# HELPERS --------------------------------------------------------------------------------


class _FakePostgresSettings(BaseCustomSettings):
    #
    # NOTE: Copied here to break these tests in case real PostgresSettings
    # really changes

    POSTGRES_HOST: str
    POSTGRES_PORT: PortInt = 5432

    POSTGRES_USER: str
    POSTGRES_PASSWORD: str

    POSTGRES_DB: str = Field(...)

    POSTGRES_MINSIZE: int = Field(1, ge=1)
    POSTGRES_MAXSIZE: int = Field(50, ge=1)

    POSTGRES_CLIENT_NAME: Optional[str] = Field(
        None,
        env=["HOST", "HOSTNAME", "POSTGRES_CLIENT_NAME"],
    )


#
# NOTE: monkeypatching envs using envfile text gets closer
#       to the real use case where .env/.env-devel
#       files are used to setup envs. Quotes formatting in
#       those files can sometimes be challenging for parsers
#
# TODO: move this to pytest_simcore ?


def setenvs_as_envfile(monkeypatch, envfile_text: str) -> EnvVarsDict:
    envs = dotenv_values(stream=StringIO(envfile_text))
    for key, value in envs.items():
        monkeypatch.setenv(key, str(value))
    return envs


def delenvs_as_envfile(monkeypatch, envfile_text: str, raising: bool) -> EnvVarsDict:
    envs = dotenv_values(stream=StringIO(envfile_text))
    for key in envs.keys():
        monkeypatch.delenv(key, raising=raising)
    return envs


# FIXTURES --------------------------------------------------------------------------------------

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


#
# NOTE: Tests below are progressive to understand and validate the construction mechanism
#       implemented in BaseCustomSettings.
#       Pay attention how the defaults of SubSettings are automaticaly captured from env vars
#       at construction time.
#


@pytest.fixture
def fake_main_settings_with_postgres():
    class _Namespace:
        #
        # Different constraints on WEBSERVER_POSTGRES subsettings
        #
        class AsRequired(BaseCustomSettings):
            # required
            WEBSERVER_POSTGRES: _FakePostgresSettings

        class AsOptionalUndefined(BaseCustomSettings):
            # optional with undefined default
            WEBSERVER_POSTGRES: Optional[_FakePostgresSettings]

        class AsOptionalAutoDefault(BaseCustomSettings):
            # optional with auto default i.e. delayed default factory
            WEBSERVER_POSTGRES: _FakePostgresSettings = Field(
                AUTO_DEFAULT_FROM_ENV_VARS
            )

        class AsNullableAutoDefault(BaseCustomSettings):
            # optional, nullable and with auto default (= enabled by default)
            WEBSERVER_POSTGRES: Optional[_FakePostgresSettings] = Field(
                AUTO_DEFAULT_FROM_ENV_VARS
            )

        class AsDefaultNone(BaseCustomSettings):
            # optional, nullable and None default (= disabled by default)
            WEBSERVER_POSTGRES: Optional[_FakePostgresSettings] = None

    return _Namespace


# TESTS --------------------------------------------------------------------------------------


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


def test_without_environs(monkeypatch, fake_main_settings_with_postgres):

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


def test_with_postgres_envs(monkeypatch, fake_main_settings_with_postgres):

    _MainSettings = fake_main_settings_with_postgres

    # environments with individual envs (PostgresSettings required fields)
    monkeypatch.delenv("WEBSERVER_POSTGRES", raising=False)
    setenvs_as_envfile(
        monkeypatch,
        """
            POSTGRES_HOST=pg
            POSTGRES_USER=test
            POSTGRES_PASSWORD=shh
            POSTGRES_DB=db
        """,
    )

    # checks

    with pytest.raises(ValidationError) as exc_info:
        s1 = _MainSettings.AsRequired.create_from_envs()

    assert exc_info.value.errors()[0] == {
        "loc": ("WEBSERVER_POSTGRES",),
        "msg": "field required",
        "type": "value_error.missing",
    }

    s2 = _MainSettings.AsOptionalUndefined.create_from_envs()
    assert s2.dict(exclude_unset=True) == {}
    assert s2.dict() == {"WEBSERVER_POSTGRES": None}

    s3 = _MainSettings.AsOptionalAutoDefault.create_from_envs()
    assert s3.dict(exclude_unset=True) == {}
    assert s3.dict() == {
        "WEBSERVER_POSTGRES": {
            "POSTGRES_HOST": "pg",
            "POSTGRES_USER": "test",
            "POSTGRES_PORT": 5432,
            "POSTGRES_PASSWORD": "shh",
            "POSTGRES_DB": "db",
            "POSTGRES_MAXSIZE": 50,
            "POSTGRES_MINSIZE": 1,
            "POSTGRES_CLIENT_NAME": None,
        }
    }

    s4 = _MainSettings.AsNullableAutoDefault.create_from_envs()
    assert s4.dict(exclude_unset=True) == {}
    assert s4.dict() == {
        "WEBSERVER_POSTGRES": {
            "POSTGRES_HOST": "pg",
            "POSTGRES_USER": "test",
            "POSTGRES_PORT": 5432,
            "POSTGRES_PASSWORD": "shh",
            "POSTGRES_DB": "db",
            "POSTGRES_MAXSIZE": 50,
            "POSTGRES_MINSIZE": 1,
            "POSTGRES_CLIENT_NAME": None,
        }
    }

    s5 = _MainSettings.AsDefaultNone.create_from_envs()
    assert s5.dict(exclude_unset=True) == {}
    assert s5.dict() == {"WEBSERVER_POSTGRES": None}


def test_with_json_env(monkeypatch, fake_main_settings_with_postgres):

    _MainSettings = fake_main_settings_with_postgres

    # environment with json (compact)
    setenvs_as_envfile(
        monkeypatch,
        """
            WEBSERVER_POSTGRES='{"POSTGRES_HOST":"pg2", "POSTGRES_USER":"test2", "POSTGRES_PASSWORD":"shh2", "POSTGRES_DB":"db2"}'
        """,
    )
    delenvs_as_envfile(
        monkeypatch,
        """
            POSTGRES_HOST=
            POSTGRES_USER=
            POSTGRES_PASSWORD=
            POSTGRES_DB=
        """,
        raising=False,
    )

    # test
    s1 = _MainSettings.AsRequired.create_from_envs()

    assert s1.dict(exclude_unset=True) == {
        "WEBSERVER_POSTGRES": {
            "POSTGRES_HOST": "pg2",
            "POSTGRES_USER": "test2",
            "POSTGRES_PASSWORD": "shh2",
            "POSTGRES_DB": "db2",
        }
    }
    assert s1.dict() == {
        "WEBSERVER_POSTGRES": {
            "POSTGRES_HOST": "pg2",
            "POSTGRES_USER": "test2",
            "POSTGRES_PORT": 5432,
            "POSTGRES_PASSWORD": "shh2",
            "POSTGRES_DB": "db2",
            "POSTGRES_MAXSIZE": 50,
            "POSTGRES_MINSIZE": 1,
            "POSTGRES_CLIENT_NAME": None,
        }
    }

    s2 = _MainSettings.AsOptionalUndefined.create_from_envs()
    assert s2.dict(exclude_unset=True) == {
        "WEBSERVER_POSTGRES": {
            "POSTGRES_HOST": "pg2",
            "POSTGRES_USER": "test2",
            "POSTGRES_PASSWORD": "shh2",
            "POSTGRES_DB": "db2",
        }
    }

    with pytest.raises(AutoDefaultFactoryError):
        s3 = _MainSettings.AsOptionalAutoDefault.create_from_envs()

    with pytest.raises(AutoDefaultFactoryError):
        s4 = _MainSettings.AsNullableAutoDefault.create_from_envs()

    s5 = _MainSettings.AsDefaultNone.create_from_envs()
    assert s5.dict(exclude_unset=True) == {
        "WEBSERVER_POSTGRES": {
            "POSTGRES_HOST": "pg2",
            "POSTGRES_USER": "test2",
            "POSTGRES_PASSWORD": "shh2",
            "POSTGRES_DB": "db2",
        }
    }


def test_with_json_and_postgres_envs(monkeypatch, fake_main_settings_with_postgres):

    _MainSettings = fake_main_settings_with_postgres

    # MIXED environment with json (compact) AND postgres envs
    setenvs_as_envfile(
        monkeypatch,
        """
            WEBSERVER_POSTGRES='{"POSTGRES_HOST":"pg2", "POSTGRES_USER":"test2", "POSTGRES_PASSWORD":"shh2", "POSTGRES_DB":"db2"}'

            POSTGRES_HOST=pg
            POSTGRES_USER=test
            POSTGRES_PASSWORD=ssh
            POSTGRES_DB=db
            POSTGRES_CLIENT_NAME=client-name
        """,
    )

    # test
    s1 = _MainSettings.AsRequired.create_from_envs()

    assert s1.dict(exclude_unset=True) == {
        "WEBSERVER_POSTGRES": {
            "POSTGRES_HOST": "pg2",
            "POSTGRES_USER": "test2",
            "POSTGRES_PASSWORD": "shh2",
            "POSTGRES_DB": "db2",
            "POSTGRES_CLIENT_NAME": "client-name",
        }
    }
    assert s1.dict() == {
        "WEBSERVER_POSTGRES": {
            "POSTGRES_HOST": "pg2",
            "POSTGRES_USER": "test2",
            "POSTGRES_PORT": 5432,
            "POSTGRES_PASSWORD": "shh2",
            "POSTGRES_DB": "db2",
            "POSTGRES_MAXSIZE": 50,
            "POSTGRES_MINSIZE": 1,
            "POSTGRES_CLIENT_NAME": "client-name",
        }
    }

    s2 = _MainSettings.AsOptionalUndefined.create_from_envs()
    assert s2.dict(exclude_unset=True) == {
        "WEBSERVER_POSTGRES": {
            "POSTGRES_HOST": "pg2",
            "POSTGRES_USER": "test2",
            "POSTGRES_PASSWORD": "shh2",
            "POSTGRES_DB": "db2",
            "POSTGRES_CLIENT_NAME": "client-name",
        }
    }

    s3 = _MainSettings.AsOptionalAutoDefault.create_from_envs()
    assert s3.dict() == {
        "WEBSERVER_POSTGRES": {
            "POSTGRES_HOST": "pg2",
            "POSTGRES_USER": "test2",
            "POSTGRES_PORT": 5432,
            "POSTGRES_PASSWORD": "shh2",
            "POSTGRES_DB": "db2",
            "POSTGRES_MAXSIZE": 50,
            "POSTGRES_MINSIZE": 1,
            "POSTGRES_CLIENT_NAME": "client-name",
        }
    }

    s4 = _MainSettings.AsNullableAutoDefault.create_from_envs()
    assert s4.dict() == {
        "WEBSERVER_POSTGRES": {
            "POSTGRES_HOST": "pg2",
            "POSTGRES_USER": "test2",
            "POSTGRES_PORT": 5432,
            "POSTGRES_PASSWORD": "shh2",
            "POSTGRES_DB": "db2",
            "POSTGRES_MAXSIZE": 50,
            "POSTGRES_MINSIZE": 1,
            "POSTGRES_CLIENT_NAME": "client-name",
        }
    }

    s5 = _MainSettings.AsDefaultNone.create_from_envs()
    assert s5.dict(exclude_unset=True) == {
        "WEBSERVER_POSTGRES": {
            "POSTGRES_HOST": "pg2",
            "POSTGRES_USER": "test2",
            "POSTGRES_PASSWORD": "shh2",
            "POSTGRES_DB": "db2",
            "POSTGRES_CLIENT_NAME": "client-name",
        }
    }
