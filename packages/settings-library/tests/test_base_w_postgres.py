# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from typing import Optional

import pytest
from pydantic import Field, ValidationError
from pytest_simcore.helpers.utils_envs import setenvs_as_envfile
from settings_library.base import (
    AUTO_DEFAULT_FROM_ENV_VARS,
    AutoDefaultFactoryError,
    BaseCustomSettings,
)
from settings_library.basic_types import PortInt

# HELPERS --------------------------------------------------------------------------------
#
# NOTE: monkeypatching envs using envfile text gets closer
#       to the real use case where .env/.env-devel
#       files are used to setup envs. Quotes formatting in
#       those files can sometimes be challenging for parsers
#


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


# FIXTURES --------------------------------------------------------------------------------------
#
# NOTE: Pydantic models are returned by function-scoped fixture such that every
#       test starts with a fresh Model class (notice that pydanctic classes involve meta-operations
#       that modify the definition of class models upon import).
#
# NOTE: all int defaults are 42, i.e. the "Answer to the Ultimate Question of Life, the Universe, and Everything"
#
# NOTE: suffixes are used to distinguis different options on the same field (e.g. _OPTIONAL, etc)
#


@pytest.fixture
def fake_main_settings_with_postgres():
    class _Namespace:
        #
        # Different constraints on WEBSERVER_POSTGRES subsettings
        # SEE test__pydantic_settings.py::test_fields_declarations for details
        #
        class AsRequired(BaseCustomSettings):
            WEBSERVER_POSTGRES: _FakePostgresSettings

        class AsNullableOptional(BaseCustomSettings):
            WEBSERVER_POSTGRES: Optional[_FakePostgresSettings]

        class AsDefaultAuto(BaseCustomSettings):
            WEBSERVER_POSTGRES: _FakePostgresSettings = Field(
                AUTO_DEFAULT_FROM_ENV_VARS
            )

        class AsNullableDefaultAuto(BaseCustomSettings):
            # optional, nullable and with auto default (= enabled by default)
            WEBSERVER_POSTGRES: Optional[_FakePostgresSettings] = Field(
                AUTO_DEFAULT_FROM_ENV_VARS
            )

        class AsNullableDefaultNull(BaseCustomSettings):
            # optional, nullable and None default (= disabled by default)
            WEBSERVER_POSTGRES: Optional[_FakePostgresSettings] = None

    return _Namespace


# TESTS --------------------------------------------------------------------------------------
#
# NOTE: Tests below are progressive to understand and validate the construction mechanism
#       implemented in BaseCustomSettings.
#       Pay attention how the defaults of SubSettings are automaticaly captured from env vars
#       at construction time.
#


def test_parse_wo_envs(fake_main_settings_with_postgres):

    _MainSettings = fake_main_settings_with_postgres

    with pytest.raises(ValidationError):
        s1 = _MainSettings.AsRequired.create_from_envs()

    s2 = _MainSettings.AsNullableOptional.create_from_envs()
    assert s2.WEBSERVER_POSTGRES == None

    with pytest.raises(AutoDefaultFactoryError):
        # auto-default cannot resolve
        s3 = _MainSettings.AsDefaultAuto.create_from_envs()

    # auto default factory resolves to None (because is nullable)
    s4 = _MainSettings.AsNullableDefaultAuto.create_from_envs()
    assert s4.WEBSERVER_POSTGRES == None

    s5 = _MainSettings.AsNullableDefaultNull.create_from_envs()
    assert s5.WEBSERVER_POSTGRES == None


def test_parse_from_postgres_envs(monkeypatch, fake_main_settings_with_postgres):

    _MainSettings = fake_main_settings_with_postgres

    # environments with individual envs (PostgresSettings required fields)
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
        _MainSettings.AsRequired.create_from_envs()

    assert exc_info.value.errors()[0] == {
        "loc": ("WEBSERVER_POSTGRES",),
        "msg": "field required",
        "type": "value_error.missing",
    }

    s2 = _MainSettings.AsNullableOptional.create_from_envs()
    assert s2.dict(exclude_unset=True) == {}
    assert s2.dict() == {"WEBSERVER_POSTGRES": None}

    s3 = _MainSettings.AsDefaultAuto.create_from_envs()
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

    s4 = _MainSettings.AsNullableDefaultAuto.create_from_envs()
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

    s5 = _MainSettings.AsNullableDefaultNull.create_from_envs()
    assert s5.dict(exclude_unset=True) == {}
    assert s5.dict() == {"WEBSERVER_POSTGRES": None}


def test_parse_from_json_env(monkeypatch, fake_main_settings_with_postgres):

    _MainSettings = fake_main_settings_with_postgres

    # environment with json (compact)
    setenvs_as_envfile(
        monkeypatch,
        """
            WEBSERVER_POSTGRES='{"POSTGRES_HOST":"pg2", "POSTGRES_USER":"test2", "POSTGRES_PASSWORD":"shh2", "POSTGRES_DB":"db2"}'
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

    s2 = _MainSettings.AsNullableOptional.create_from_envs()
    assert s2.dict(exclude_unset=True) == {
        "WEBSERVER_POSTGRES": {
            "POSTGRES_HOST": "pg2",
            "POSTGRES_USER": "test2",
            "POSTGRES_PASSWORD": "shh2",
            "POSTGRES_DB": "db2",
        }
    }

    with pytest.raises(AutoDefaultFactoryError):
        s3 = _MainSettings.AsDefaultAuto.create_from_envs()

    s4 = _MainSettings.AsNullableDefaultAuto.create_from_envs()
    assert s4.dict(exclude_unset=True) == {
        "WEBSERVER_POSTGRES": {
            "POSTGRES_HOST": "pg2",
            "POSTGRES_USER": "test2",
            "POSTGRES_PASSWORD": "shh2",
            "POSTGRES_DB": "db2",
        }
    }

    s5 = _MainSettings.AsNullableDefaultNull.create_from_envs()
    assert s5.dict(exclude_unset=True) == {
        "WEBSERVER_POSTGRES": {
            "POSTGRES_HOST": "pg2",
            "POSTGRES_USER": "test2",
            "POSTGRES_PASSWORD": "shh2",
            "POSTGRES_DB": "db2",
        }
    }


def test_parse_from_mixed_envs(monkeypatch, fake_main_settings_with_postgres):

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

    s2 = _MainSettings.AsNullableOptional.create_from_envs()
    assert s2.dict(exclude_unset=True) == {
        "WEBSERVER_POSTGRES": {
            "POSTGRES_HOST": "pg2",
            "POSTGRES_USER": "test2",
            "POSTGRES_PASSWORD": "shh2",
            "POSTGRES_DB": "db2",
            "POSTGRES_CLIENT_NAME": "client-name",
        }
    }

    s3 = _MainSettings.AsDefaultAuto.create_from_envs()
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

    s4 = _MainSettings.AsNullableDefaultAuto.create_from_envs()
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

    s5 = _MainSettings.AsNullableDefaultNull.create_from_envs()
    assert s5.dict(exclude_unset=True) == {
        "WEBSERVER_POSTGRES": {
            "POSTGRES_HOST": "pg2",
            "POSTGRES_USER": "test2",
            "POSTGRES_PASSWORD": "shh2",
            "POSTGRES_DB": "db2",
            "POSTGRES_CLIENT_NAME": "client-name",
        }
    }


def test_toggle_plugin_1(monkeypatch, fake_main_settings_with_postgres):
    _MainSettings = fake_main_settings_with_postgres

    # NOTE: let's focus on setups #4 and #5
    #
    #  Using nullable fields for subsettings, allows us to easily mark a module as
    #  enabled/disabled
    #

    # empty environ

    s4 = (
        _MainSettings.AsNullableDefaultAuto.create_from_envs()
    )  # cannot resolve default, then null -> disabled
    s5 = _MainSettings.AsNullableDefaultNull.create_from_envs()  # disabled by default

    assert s4.WEBSERVER_POSTGRES is None
    assert s5.WEBSERVER_POSTGRES is None


def test_toggle_plugin_2(monkeypatch, fake_main_settings_with_postgres):
    _MainSettings = fake_main_settings_with_postgres

    # minimal
    setenvs_as_envfile(
        monkeypatch,
        """
        POSTGRES_HOST=pg
        POSTGRES_USER=test
        POSTGRES_PASSWORD=ssh
        POSTGRES_DB=db
    """,
    )

    s4 = _MainSettings.AsNullableDefaultAuto.create_from_envs()
    s5 = _MainSettings.AsNullableDefaultNull.create_from_envs()  # disabled by default

    assert s4.WEBSERVER_POSTGRES is not None
    assert s5.WEBSERVER_POSTGRES is None


def test_toggle_plugin_3(monkeypatch, fake_main_settings_with_postgres):
    _MainSettings = fake_main_settings_with_postgres

    # explicitly disables
    setenvs_as_envfile(
        monkeypatch,
        """
        WEBSERVER_POSTGRES=null

        POSTGRES_HOST=pg
        POSTGRES_USER=test
        POSTGRES_PASSWORD=ssh
        POSTGRES_DB=db
        """,
    )

    s4 = _MainSettings.AsNullableDefaultAuto.create_from_envs()
    s5 = _MainSettings.AsNullableDefaultNull.create_from_envs()

    assert s4.WEBSERVER_POSTGRES is None
    assert s5.WEBSERVER_POSTGRES is None


def test_toggle_plugin_4(monkeypatch, fake_main_settings_with_postgres):
    _MainSettings = fake_main_settings_with_postgres

    # Enables both
    setenvs_as_envfile(
        monkeypatch,
        """
        WEBSERVER_POSTGRES='{"POSTGRES_HOST":"pg2", "POSTGRES_USER":"test2", "POSTGRES_PASSWORD":"shh2", "POSTGRES_DB":"db2"}'

        POSTGRES_HOST=pg
        POSTGRES_USER=test
        POSTGRES_PASSWORD=ssh
        POSTGRES_DB=db
        """,
    )
    s4 = _MainSettings.AsNullableDefaultAuto.create_from_envs()
    s5 = _MainSettings.AsNullableDefaultNull.create_from_envs()

    assert s4.WEBSERVER_POSTGRES is not None
    assert s5.WEBSERVER_POSTGRES is not None
    assert s4 == s5


def test_toggle_plugin_5(monkeypatch, fake_main_settings_with_postgres):
    _MainSettings = fake_main_settings_with_postgres

    # Enables both
    setenvs_as_envfile(
        monkeypatch,
        """
        WEBSERVER_POSTGRES='{"POSTGRES_HOST":"pg2", "POSTGRES_USER":"test2", "POSTGRES_PASSWORD":"shh2", "POSTGRES_DB":"db2"}'
        """,
    )
    s4 = _MainSettings.AsNullableDefaultAuto.create_from_envs()
    s5 = _MainSettings.AsNullableDefaultNull.create_from_envs()

    assert s4.WEBSERVER_POSTGRES is not None
    assert s5.WEBSERVER_POSTGRES is not None
    assert s4 == s5
