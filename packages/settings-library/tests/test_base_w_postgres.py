# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import os
from collections.abc import Callable

import pytest
from pydantic import AliasChoices, Field, ValidationError
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_envfile
from settings_library.base import BaseCustomSettings, DefaultFromEnvFactoryError
from settings_library.basic_types import PortInt

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
def postgres_envvars_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in os.environ:
        if name.startswith("POSTGRES_"):
            monkeypatch.delenv(name)


@pytest.fixture
def model_classes_factory() -> Callable:
    #
    # pydantic uses a meta-class to build the actual class model using
    # the user's annotations. This fixture allows us to control the moment
    # this happens (e.g. to guarantee certain)
    #

    def _create_classes():
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

            POSTGRES_CLIENT_NAME: str | None = Field(
                None,
                validation_alias=AliasChoices(
                    "HOST", "HOSTNAME", "POSTGRES_CLIENT_NAME"
                ),
            )

        #
        # Different constraints on WEBSERVER_POSTGRES subsettings
        # SEE test__pydantic_settings.py::test_fields_declarations for details
        #
        class S1(BaseCustomSettings):
            WEBSERVER_POSTGRES: _FakePostgresSettings

        class S2(BaseCustomSettings):
            WEBSERVER_POSTGRES_NULLABLE_OPTIONAL: _FakePostgresSettings | None = None

        class S3(BaseCustomSettings):
            # cannot be disabled!!
            WEBSERVER_POSTGRES_DEFAULT_ENV: _FakePostgresSettings = Field(
                json_schema_extra={"auto_default_from_env": True}
            )

        class S4(BaseCustomSettings):
            # defaults enabled but if cannot be resolved, it disables
            WEBSERVER_POSTGRES_NULLABLE_DEFAULT_ENV: _FakePostgresSettings | None = (
                Field(json_schema_extra={"auto_default_from_env": True})
            )

        class S5(BaseCustomSettings):
            # defaults disabled but only explicit enabled
            WEBSERVER_POSTGRES_NULLABLE_DEFAULT_NULL: _FakePostgresSettings | None = (
                None
            )

        return (
            S1,
            S2,
            S3,
            S4,
            S5,
        )

    return _create_classes


#
# NOTE: Tests below are progressive to understand and validate the construction mechanism
#       implemented in BaseCustomSettings.
#       Pay attention how the defaults of SubSettings are automaticaly captured from env vars
#       at construction time.
#
# NOTE: pytest.MonkeyPatching envs using envfile text gets the tests closer
#       to the real use case where .env/.env-devel
#       files are used to setup envs. Quotes formatting in
#       those files can sometimes be challenging for parsers
#


def test_parse_from_empty_envs(
    postgres_envvars_unset: None, model_classes_factory: Callable
):

    S1, S2, S3, S4, S5 = model_classes_factory()

    with pytest.raises(ValidationError, match="WEBSERVER_POSTGRES") as exc_info:
        S1()

    validation_error = exc_info.value
    assert validation_error.error_count() == 1
    error = validation_error.errors()[0]
    assert error["type"] == "missing"
    assert error["input"] == {}

    s2 = S2()
    assert s2.WEBSERVER_POSTGRES_NULLABLE_OPTIONAL is None

    with pytest.raises(DefaultFromEnvFactoryError) as exc_info:
        # NOTE: cannot have a default or assignment
        S3()

    assert len(exc_info.value.errors) == 4, "Default could not be constructed"

    # auto default factory resolves to None (because is nullable)
    s4 = S4()
    assert s4.WEBSERVER_POSTGRES_NULLABLE_DEFAULT_ENV is None

    s5 = S5()
    assert s5.WEBSERVER_POSTGRES_NULLABLE_DEFAULT_NULL is None


def test_parse_from_individual_envs(
    postgres_envvars_unset: None,
    monkeypatch: pytest.MonkeyPatch,
    model_classes_factory: Callable,
):

    S1, S2, S3, S4, S5 = model_classes_factory()

    # environment
    #  - with individual envs (PostgresSettings required fields)
    setenvs_from_envfile(
        monkeypatch,
        """
            POSTGRES_HOST=pg
            POSTGRES_USER=test
            POSTGRES_PASSWORD=shh
            POSTGRES_DB=db
        """,
    )

    with pytest.raises(ValidationError) as exc_info:
        S1()

    assert exc_info.value.errors()[0] == {
        "input": {},
        "loc": ("WEBSERVER_POSTGRES",),
        "msg": "Field required",
        "type": "missing",
        "url": "https://errors.pydantic.dev/2.9/v/missing",
    }

    s2 = S2()
    assert s2.model_dump(exclude_unset=True) == {}
    assert s2.model_dump() == {"WEBSERVER_POSTGRES_NULLABLE_OPTIONAL": None}

    s3 = S3()
    assert s3.model_dump(exclude_unset=True) == {}
    assert s3.model_dump() == {
        "WEBSERVER_POSTGRES_DEFAULT_ENV": {
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

    s4 = S4()
    assert s4.model_dump(exclude_unset=True) == {}
    assert s4.model_dump() == {
        "WEBSERVER_POSTGRES_NULLABLE_DEFAULT_ENV": {
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

    s5 = S5()
    assert s5.model_dump(exclude_unset=True) == {}
    assert s5.model_dump() == {"WEBSERVER_POSTGRES_NULLABLE_DEFAULT_NULL": None}


def test_parse_compact_env(
    postgres_envvars_unset: None, monkeypatch, model_classes_factory
):

    S1, S2, S3, S4, S5 = model_classes_factory()

    # environment
    # - with json (compact)
    JSON_VALUE = '{"POSTGRES_HOST":"pg2", "POSTGRES_USER":"test2", "POSTGRES_PASSWORD":"shh2", "POSTGRES_DB":"db2"}'

    with monkeypatch.context() as patch:
        setenvs_from_envfile(
            patch,
            f"""
                WEBSERVER_POSTGRES='{JSON_VALUE}'
            """,
        )

        # test
        s1 = S1()

        assert s1.model_dump(exclude_unset=True) == {
            "WEBSERVER_POSTGRES": {
                "POSTGRES_HOST": "pg2",
                "POSTGRES_USER": "test2",
                "POSTGRES_PASSWORD": "shh2",
                "POSTGRES_DB": "db2",
            }
        }
        assert s1.model_dump() == {
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

    with monkeypatch.context() as patch:
        setenvs_from_envfile(
            patch,
            f"""
                WEBSERVER_POSTGRES_NULLABLE_OPTIONAL='{JSON_VALUE}'
            """,
        )
        s2 = S2()
        assert s2.model_dump(exclude_unset=True) == {
            "WEBSERVER_POSTGRES_NULLABLE_OPTIONAL": {
                "POSTGRES_HOST": "pg2",
                "POSTGRES_USER": "test2",
                "POSTGRES_PASSWORD": "shh2",
                "POSTGRES_DB": "db2",
            }
        }

    with monkeypatch.context() as patch:
        setenvs_from_envfile(
            patch,
            f"""
                WEBSERVER_POSTGRES_DEFAULT_ENV='{JSON_VALUE}'
            """,
        )
        # NOTE: pydantic 1.9 does it right: it delays evaluating
        # default until it is really needed. Here before it would
        # fail because default cannot be computed even if the final value can!
        s3 = S3()
        assert s3.model_dump(exclude_unset=True) == {
            "WEBSERVER_POSTGRES_DEFAULT_ENV": {
                "POSTGRES_HOST": "pg2",
                "POSTGRES_USER": "test2",
                "POSTGRES_PASSWORD": "shh2",
                "POSTGRES_DB": "db2",
            }
        }

    with monkeypatch.context() as patch:
        setenvs_from_envfile(
            patch,
            f"""
                WEBSERVER_POSTGRES_NULLABLE_DEFAULT_ENV='{JSON_VALUE}'
            """,
        )
        s4 = S4()
        assert s4.model_dump(exclude_unset=True) == {
            "WEBSERVER_POSTGRES_NULLABLE_DEFAULT_ENV": {
                "POSTGRES_HOST": "pg2",
                "POSTGRES_USER": "test2",
                "POSTGRES_PASSWORD": "shh2",
                "POSTGRES_DB": "db2",
            }
        }

    with monkeypatch.context() as patch:
        setenvs_from_envfile(
            patch,
            f"""
                WEBSERVER_POSTGRES_NULLABLE_DEFAULT_NULL='{JSON_VALUE}'
            """,
        )
        s5 = S5()
        assert s5.model_dump(exclude_unset=True) == {
            "WEBSERVER_POSTGRES_NULLABLE_DEFAULT_NULL": {
                "POSTGRES_HOST": "pg2",
                "POSTGRES_USER": "test2",
                "POSTGRES_PASSWORD": "shh2",
                "POSTGRES_DB": "db2",
            }
        }


def test_parse_from_mixed_envs(
    postgres_envvars_unset: None, monkeypatch, model_classes_factory
):

    S1, S2, S3, S4, S5 = model_classes_factory()

    # environment
    # - Mixed with json (compact) AND postgres envs
    ENV_FILE = """
            {0}='{{"POSTGRES_HOST":"pg2", "POSTGRES_USER":"test2", "POSTGRES_PASSWORD":"shh2", "POSTGRES_DB":"db2"}}'

            POSTGRES_HOST=pg
            POSTGRES_USER=test
            POSTGRES_PASSWORD=ssh
            POSTGRES_DB=db
        """

    with monkeypatch.context():
        setenvs_from_envfile(
            monkeypatch,
            ENV_FILE.format("WEBSERVER_POSTGRES"),
        )

        s1 = S1()

        assert s1.model_dump() == {
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
        # NOTE how unset marks also applies to embedded fields
        # NOTE: (1) priority of json-compact over granulated
        # NOTE: (2) json-compact did not define this but granulated did
        assert s1.model_dump(exclude_unset=True) == {
            "WEBSERVER_POSTGRES": {
                "POSTGRES_HOST": "pg2",  # <- (1)
                "POSTGRES_USER": "test2",  # <- (1)
                "POSTGRES_PASSWORD": "shh2",  # <- (1)
                "POSTGRES_DB": "db2",  # <- (1)
            }
        }

    with monkeypatch.context():
        setenvs_from_envfile(
            monkeypatch,
            ENV_FILE.format("WEBSERVER_POSTGRES_NULLABLE_OPTIONAL"),
        )

        s2 = S2()
        assert s2.model_dump(exclude_unset=True) == {
            "WEBSERVER_POSTGRES_NULLABLE_OPTIONAL": {
                "POSTGRES_HOST": "pg2",
                "POSTGRES_USER": "test2",
                "POSTGRES_PASSWORD": "shh2",
                "POSTGRES_DB": "db2",
            }
        }

    with monkeypatch.context():
        setenvs_from_envfile(
            monkeypatch,
            ENV_FILE.format("WEBSERVER_POSTGRES_DEFAULT_ENV"),
        )

        s3 = S3()
        assert s3.model_dump(exclude_unset=True) == {
            "WEBSERVER_POSTGRES_DEFAULT_ENV": {
                "POSTGRES_HOST": "pg2",
                "POSTGRES_USER": "test2",
                "POSTGRES_PASSWORD": "shh2",
                "POSTGRES_DB": "db2",
            }
        }

    with monkeypatch.context():
        setenvs_from_envfile(
            monkeypatch,
            ENV_FILE.format("WEBSERVER_POSTGRES_NULLABLE_DEFAULT_ENV"),
        )

        s4 = S4()
        assert s4.model_dump(exclude_unset=True) == {
            "WEBSERVER_POSTGRES_NULLABLE_DEFAULT_ENV": {
                "POSTGRES_HOST": "pg2",
                "POSTGRES_USER": "test2",
                "POSTGRES_PASSWORD": "shh2",
                "POSTGRES_DB": "db2",
            }
        }

    with monkeypatch.context():
        setenvs_from_envfile(
            monkeypatch,
            ENV_FILE.format("WEBSERVER_POSTGRES_NULLABLE_DEFAULT_NULL"),
        )

        s5 = S5()
        assert s5.model_dump(exclude_unset=True) == {
            "WEBSERVER_POSTGRES_NULLABLE_DEFAULT_NULL": {
                "POSTGRES_HOST": "pg2",
                "POSTGRES_USER": "test2",
                "POSTGRES_PASSWORD": "shh2",
                "POSTGRES_DB": "db2",
            }
        }


# NOTE: let's focus on setups #4 and #5
#
#  Using nullable fields for subsettings, allows us to easily mark a module as
#  enabled/disabled
#
#   - S3: cannot be disabled!! (e.g. can be used for system add-ons)
#        *_DEFAULT_ENV: S = Field( auto_default_from_env=True )
#
#   - S4: defaults enabled but if cannot be resolved, it disables
#         *_NULLABLE_DEFAULT_ENV: Optional[S] = Field(auto_default_from_env=True)
#
#   - S5: defaults disabled but only explicit enabled
#         *_NULLABLE_DEFAULT_NULL: Optional[S] = None
#


def test_toggle_plugin_1(
    postgres_envvars_unset: None, monkeypatch, model_classes_factory
):

    *_, S4, S5 = model_classes_factory()

    # empty environ

    s4 = S4()  # cannot resolve default, then null -> disabled
    s5 = S5()  # disabled by default

    assert s4.WEBSERVER_POSTGRES_NULLABLE_DEFAULT_ENV is None
    assert s5.WEBSERVER_POSTGRES_NULLABLE_DEFAULT_NULL is None


def test_toggle_plugin_2(
    postgres_envvars_unset: None, monkeypatch, model_classes_factory
):
    *_, S4, S5 = model_classes_factory()

    # minimal
    setenvs_from_envfile(
        monkeypatch,
        """
        POSTGRES_HOST=pg
        POSTGRES_USER=test
        POSTGRES_PASSWORD=ssh
        POSTGRES_DB=db
    """,
    )

    s4 = S4()
    s5 = S5()  # disabled by default

    assert s4.WEBSERVER_POSTGRES_NULLABLE_DEFAULT_ENV is not None
    assert s5.WEBSERVER_POSTGRES_NULLABLE_DEFAULT_NULL is None


def test_toggle_plugin_3(
    postgres_envvars_unset: None, monkeypatch, model_classes_factory
):
    *_, S4, S5 = model_classes_factory()

    # explicitly disables
    setenvs_from_envfile(
        monkeypatch,
        """
        WEBSERVER_POSTGRES_NULLABLE_DEFAULT_ENV=null

        POSTGRES_HOST=pg
        POSTGRES_USER=test
        POSTGRES_PASSWORD=ssh
        POSTGRES_DB=db
        """,
    )

    s4 = S4()
    s5 = S5()

    assert s4.WEBSERVER_POSTGRES_NULLABLE_DEFAULT_ENV is None
    assert s5.WEBSERVER_POSTGRES_NULLABLE_DEFAULT_NULL is None


def test_toggle_plugin_4(
    postgres_envvars_unset: None, monkeypatch, model_classes_factory
):

    *_, S4, S5 = model_classes_factory()
    JSON_VALUE = '{"POSTGRES_HOST":"pg2", "POSTGRES_USER":"test2", "POSTGRES_PASSWORD":"shh2", "POSTGRES_DB":"db2"}'

    with monkeypatch.context() as patch:
        # Enables both
        setenvs_from_envfile(
            patch,
            f"""
            WEBSERVER_POSTGRES_NULLABLE_DEFAULT_ENV='{JSON_VALUE}'
            WEBSERVER_POSTGRES_NULLABLE_DEFAULT_NULL='{JSON_VALUE}'

            POSTGRES_HOST=pg
            POSTGRES_USER=test
            POSTGRES_PASSWORD=ssh
            POSTGRES_DB=db
            POSTGRES_CLIENT_NAME=name-is-now-set
            """,
        )
        s4 = S4()
        s5 = S5()

        assert s4.WEBSERVER_POSTGRES_NULLABLE_DEFAULT_ENV is not None
        assert s5.WEBSERVER_POSTGRES_NULLABLE_DEFAULT_NULL is not None
        assert (
            s4.WEBSERVER_POSTGRES_NULLABLE_DEFAULT_ENV
            == s5.WEBSERVER_POSTGRES_NULLABLE_DEFAULT_NULL
        )

    with monkeypatch.context() as patch:

        # Enables both but remove individuals
        setenvs_from_envfile(
            patch,
            f"""
            WEBSERVER_POSTGRES_NULLABLE_DEFAULT_ENV='{JSON_VALUE}'
            WEBSERVER_POSTGRES_NULLABLE_DEFAULT_NULL='{JSON_VALUE}'
            """,
        )
        s4 = S4()
        s5 = S5()

        assert s4.WEBSERVER_POSTGRES_NULLABLE_DEFAULT_ENV is not None
        assert s5.WEBSERVER_POSTGRES_NULLABLE_DEFAULT_NULL is not None
        assert (
            s4.WEBSERVER_POSTGRES_NULLABLE_DEFAULT_ENV
            == s5.WEBSERVER_POSTGRES_NULLABLE_DEFAULT_NULL
        )
