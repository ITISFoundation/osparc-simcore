# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import importlib
import inspect
import os
from io import StringIO
from pathlib import Path
from typing import List, Optional, Type

import pytest
import settings_library
from dotenv import dotenv_values
from pydantic import BaseModel, Field, ValidationError
from pydantic.env_settings import BaseSettings
from pytest_simcore.helpers.utils_environs import EnvVarsDict
from settings_library.base import AUTO_DEFAULT_FROM_ENV_VARS, BaseCustomSettings
from settings_library.postgres import PostgresSettings

# HELPERS --------------------------------------------------------------------------------


def _get_all_settings_classes_in_library() -> List[Type[BaseSettings]]:

    modules = [
        importlib.import_module(f"settings_library.{p.name[:-3]}")
        for p in Path(settings_library.__file__).parent.glob("*.py")
        if not p.name.endswith("__init__.py")
    ]
    assert modules

    classes = [
        cls
        for mod in modules
        for _, cls in inspect.getmembers(mod, inspect.isclass)
        if issubclass(cls, BaseSettings) and cls != BaseSettings
    ]
    assert classes

    return classes


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
def fake_sub_model_class():
    # NOTE: that this class inherits from BaseModel (not BaseSettings)
    # Typically used as a json-like environ
    class _SubModel(BaseModel):
        SUBMODEL_VALUE: int
        SUBMODEL_VALUE_DEFAULT: int = 42
        SUBMODEL_VALUE_OPTIONAL: Optional[int]
        SUBMODEL_VALUE_OPTIONAL_DEFAULT_VALUE: Optional[int] = 42
        SUBMODEL_VALUE_OPTIONAL_DEFAULT_NONE: Optional[int] = None

    return _SubModel


@pytest.fixture
def fake_sub_settings_class():
    # NOTE: that this class inherits from BaseSettings
    # Typically used to capture env vars for a shared module (e.g. postgres) and
    # embed them in a general settings
    class _SubSettings(BaseCustomSettings):
        SUBSETTINGS_VALUE: int
        SUBSETTINGS_VALUE_DEFAULT: int = 42
        SUBSETTINGS_VALUE_OPTIONAL: Optional[int]
        SUBSETTINGS_VALUE_OPTIONAL_DEFAULT_VALUE: Optional[int] = 42
        SUBSETTINGS_VALUE_OPTIONAL_DEFAULT_NONE: Optional[int] = None

    return _SubSettings


@pytest.fixture
def fake_main_settings_class(fake_sub_model_class, fake_sub_settings_class):
    # NOTE: _SubModel is a BaseModel and _SubSettings is a BaseSettings
    _SubSettings = fake_sub_settings_class
    _SubModel = fake_sub_model_class

    # NOTE: the constraints on the 'int' fields within _SubSettings/_SubModel
    #       are also repricated with '_SubSettings' fields within _MainSettings
    class _MainSettings(BaseCustomSettings):
        MAIN_MODULE: _SubSettings
        MAIN_MODULE_DEFAULT: _SubSettings = Field(default=AUTO_DEFAULT_FROM_ENV_VARS)
        MAIN_MODULE_OPTIONAL: Optional[_SubSettings]
        MAIN_MODULE_OPTIONAL_DEFAULT_VALUE: Optional[_SubSettings] = Field(
            default=AUTO_DEFAULT_FROM_ENV_VARS
        )
        MAIN_MODULE_OPTIONAL_DEFAULT_NONE: Optional[_SubSettings] = None

        MAIN_GROUP: _SubModel

    return _MainSettings


# TESTS -----------------------------------------------------------------------------------------------------
#
# NOTE: Tests below are progressive to understand and validate the construction mechanism
#       implemented in BaseCustomSettings.
#       Pay attention how the defaults of SubSettings are automaticaly captured from env vars
#       at construction time.
#


def test_create_settings_from_env(monkeypatch, fake_sub_settings_class):
    _SubSettings = fake_sub_settings_class

    # environments
    monkeypatch.setenv("SUBSETTINGS_VALUE", 1)

    # create
    settings = _SubSettings.create_from_envs()

    # check
    assert settings.dict() == {
        "SUBSETTINGS_VALUE": 1,
        "SUBSETTINGS_VALUE_DEFAULT": 42,
        "SUBSETTINGS_VALUE_OPTIONAL": None,
        "SUBSETTINGS_VALUE_OPTIONAL_DEFAULT_VALUE": 42,
        "SUBSETTINGS_VALUE_OPTIONAL_DEFAULT_NONE": None,
    }

    assert settings.dict(exclude_unset=True) == {
        "SUBSETTINGS_VALUE": 1,
    }


def test_create_main_settings_from_env(monkeypatch, fake_main_settings_class):
    _MainSettings = fake_main_settings_class

    # environments
    #  - 'SUBSETTINGS_VALUE=42' is used to auto-create default, i.e. sets MAIN_MODULE_DEFAULT because _SubSettings requires it
    monkeypatch.setenv("MAIN_MODULE", '{"SUBSETTINGS_VALUE": 1}')
    monkeypatch.setenv("SUBSETTINGS_VALUE", "42")
    monkeypatch.setenv("MAIN_GROUP", '{"SUBMODEL_VALUE": 1}')

    # create
    settings = _MainSettings.create_from_envs()

    # check
    assert settings.dict() == {
        "MAIN_MODULE": {
            "SUBSETTINGS_VALUE": 1,
            "SUBSETTINGS_VALUE_DEFAULT": 42,
            "SUBSETTINGS_VALUE_OPTIONAL": None,
            "SUBSETTINGS_VALUE_OPTIONAL_DEFAULT_VALUE": 42,
            "SUBSETTINGS_VALUE_OPTIONAL_DEFAULT_NONE": None,
        },
        "MAIN_MODULE_DEFAULT": {
            "SUBSETTINGS_VALUE": 42,
            "SUBSETTINGS_VALUE_DEFAULT": 42,
            "SUBSETTINGS_VALUE_OPTIONAL": None,
            "SUBSETTINGS_VALUE_OPTIONAL_DEFAULT_VALUE": 42,
            "SUBSETTINGS_VALUE_OPTIONAL_DEFAULT_NONE": None,
        },
        "MAIN_MODULE_OPTIONAL": None,
        "MAIN_MODULE_OPTIONAL_DEFAULT_VALUE": {
            "SUBSETTINGS_VALUE": 42,
            "SUBSETTINGS_VALUE_DEFAULT": 42,
            "SUBSETTINGS_VALUE_OPTIONAL": None,
            "SUBSETTINGS_VALUE_OPTIONAL_DEFAULT_VALUE": 42,
            "SUBSETTINGS_VALUE_OPTIONAL_DEFAULT_NONE": None,
        },
        "MAIN_MODULE_OPTIONAL_DEFAULT_NONE": None,
        "MAIN_GROUP": {
            "SUBMODEL_VALUE": 1,
            "SUBMODEL_VALUE_DEFAULT": 42,
            "SUBMODEL_VALUE_OPTIONAL": None,
            "SUBMODEL_VALUE_OPTIONAL_DEFAULT_VALUE": 42,
            "SUBMODEL_VALUE_OPTIONAL_DEFAULT_NONE": None,
        },
    }

    assert settings.dict(exclude_unset=True) == {
        "MAIN_MODULE": {
            "SUBSETTINGS_VALUE": 1,
        },
        "MAIN_GROUP": {"SUBMODEL_VALUE": 1},
    }


def test_create_from_envs_1(monkeypatch, fake_sub_model_class, fake_sub_settings_class):
    _SubSettings = fake_sub_settings_class

    class _MainSettings(BaseCustomSettings):
        MAIN_MODULE: _SubSettings
        # - is embedded settings
        # - is required

    # environments
    monkeypatch.setenv("MAIN_MODULE", '{"SUBSETTINGS_VALUE": 1}')

    # create
    settings = _MainSettings.create_from_envs()

    # check
    assert settings.dict() == {
        "MAIN_MODULE": {
            "SUBSETTINGS_VALUE": 1,
            "SUBSETTINGS_VALUE_DEFAULT": 42,
            "SUBSETTINGS_VALUE_OPTIONAL": None,
            "SUBSETTINGS_VALUE_OPTIONAL_DEFAULT_VALUE": 42,
            "SUBSETTINGS_VALUE_OPTIONAL_DEFAULT_NONE": None,
        },
    }

    assert settings.dict(exclude_unset=True) == {
        "MAIN_MODULE": {"SUBSETTINGS_VALUE": 1}
    }


def test_create_from_envs_2(monkeypatch, fake_sub_model_class, fake_sub_settings_class):
    _SubSettings = fake_sub_settings_class

    class _MainSettings(BaseCustomSettings):
        MAIN_MODULE: Optional[_SubSettings]
        # - is embedded settings
        # - is optional
        # - undefined default

    # environments

    # create
    settings = _MainSettings.create_from_envs()

    # check
    assert settings.dict() == {"MAIN_MODULE": None}

    assert settings.dict(exclude_unset=True) == {}


def test_create_from_envs_3(monkeypatch, fake_sub_model_class, fake_sub_settings_class):
    _SubSettings = fake_sub_settings_class

    class _MainSettings(BaseCustomSettings):
        MAIN_MODULE: Optional[_SubSettings] = None
        # - is embedded settings
        # - is optional
        # - default is None

    # environments

    # create
    settings = _MainSettings.create_from_envs()

    # check
    assert settings.dict() == {"MAIN_MODULE": None}

    assert settings.dict(exclude_unset=True) == {}


def test_create_from_envs_4(monkeypatch, fake_sub_model_class, fake_sub_settings_class):
    _SubSettings = fake_sub_settings_class

    class _MainSettings(BaseCustomSettings):
        MAIN_MODULE: Optional[_SubSettings] = Field(default=AUTO_DEFAULT_FROM_ENV_VARS)
        # - is embedded settings
        # - is optional
        # - default is auto (i.e. will capture default from env vars u)

    # environments
    # NOTE: this is a field from _SubSettings!!
    monkeypatch.setenv("SUBSETTINGS_VALUE", "1")

    # create
    settings = _MainSettings.create_from_envs()

    # check
    assert settings.dict() == {
        "MAIN_MODULE": {
            "SUBSETTINGS_VALUE": 1,
            "SUBSETTINGS_VALUE_DEFAULT": 42,
            "SUBSETTINGS_VALUE_OPTIONAL": None,
            "SUBSETTINGS_VALUE_OPTIONAL_DEFAULT_VALUE": 42,
            "SUBSETTINGS_VALUE_OPTIONAL_DEFAULT_NONE": None,
        },
    }

    assert settings.dict(exclude_unset=True) == {}  # NOTE that ALL are defaults!

    # QUESTION: should auto-default raise if cannot be init or be set to None?


@pytest.fixture
def fake_main_settings_with_postgres():
    class _MainSettingsVariants:
        #
        # Different constraints on WEBSERVER_POSTGRES subsettings
        #
        class AsRequired(BaseCustomSettings):
            # required
            WEBSERVER_POSTGRES: PostgresSettings

        class AsOptionalUndefined(BaseCustomSettings):
            # optional with undefined default
            WEBSERVER_POSTGRES: Optional[PostgresSettings]

        class AsOptionalAutoDefault(BaseCustomSettings):
            # optional with auto default i.e. delayed default factory
            WEBSERVER_POSTGRES: PostgresSettings = Field(AUTO_DEFAULT_FROM_ENV_VARS)

        class AsNullableAutoDefault(BaseCustomSettings):
            # optional, nullable and with auto default (= enabled by default)
            WEBSERVER_POSTGRES: Optional[PostgresSettings] = Field(
                AUTO_DEFAULT_FROM_ENV_VARS
            )

        class AsDefaultNone(BaseCustomSettings):
            # optional, nullable and None default (= disabled by default)
            WEBSERVER_POSTGRES: Optional[PostgresSettings] = None

    return _MainSettingsVariants


def test_create_from_envs_5(monkeypatch, fake_main_settings_with_postgres):

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


def test_create_from_envs_6(monkeypatch, fake_main_settings_with_postgres):

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
    assert s3.dict(exclude_unset=True) == {
        "WEBSERVER_POSTGRES": {
            "POSTGRES_HOST": "pg",
            "POSTGRES_USER": "test",
            "POSTGRES_PASSWORD": "shh",
            "POSTGRES_DB": "db",
        }
    }

    s4 = _MainSettings.AsNullableAutoDefault.create_from_envs()
    s5 = _MainSettings.AsDefaultNone.create_from_envs()


def test_create_from_envs_7(monkeypatch, fake_main_settings_with_postgres):

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


@pytest.mark.skip(reason="FIXME: WIP!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
@pytest.mark.parametrize("env_file", (".env-sample", ".env-fails"))
def test_create_settings_from_envs(
    env_file: str, mock_environment: EnvVarsDict, fake_settings_class
):

    assert all(
        os.environ[env_name] == env_value
        for env_name, env_value in mock_environment.items()
    )

    if "fail" in env_file:
        with pytest.raises(ValidationError):
            settings = fake_settings_class.create_from_envs()
    else:
        settings = fake_settings_class.create_from_envs()

        # some expected values
        assert mock_environment["APP_PORT"]
        assert settings.APP_PORT == int(mock_environment["APP_PORT"])

        assert settings.APP_POSTGRES


@pytest.mark.parametrize(
    "lib_settings_cls",
    _get_all_settings_classes_in_library(),
    ids=lambda cls: cls.__name__,
)
def test_polices_in_library_class_settings(lib_settings_cls):
    # must inherit
    assert issubclass(lib_settings_cls, BaseCustomSettings)

    # all fields UPPER
    assert all(key == key.upper() for key in lib_settings_cls.__fields__.keys())
