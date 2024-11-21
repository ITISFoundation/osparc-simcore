# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=protected-access

import json
from collections.abc import Callable
from typing import Any

import pytest
import settings_library.base
from pydantic import BaseModel, ValidationError
from pydantic.fields import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from pytest_mock import MockerFixture
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_envfile
from pytest_simcore.helpers.typing_env import EnvVarsDict
from settings_library.base import (
    _AUTO_DEFAULT_FACTORY_RESOLVES_TO_NONE_FSTRING,
    BaseCustomSettings,
    DefaultFromEnvFactoryError,
)
from settings_library.email import SMTPSettings

S2 = json.dumps({"S_VALUE": 2})
S3 = json.dumps({"S_VALUE": 3})


def _get_attrs_tree(obj: Any) -> dict[str, Any]:
    # long version of json.dumps({ k:str(getattr(field,k)) for k in ModelField.__slots__ } )
    tree = {}
    for name in obj.__class__.__slots__:
        value = getattr(obj, name)
        if hasattr(value.__class__, "__slots__"):
            tree[name] = _get_attrs_tree(value)
        else:
            tree[name] = f"{value}"

    return tree


def _print_defaults(model_cls: type[BaseModel]):
    for name, field in model_cls.model_fields.items():
        print(name, ":", end="")
        try:
            default = field.get_default(call_default_factory=True)  # new in Pydatic v2
            print(default, type(default))
        except ValidationError as err:
            print(err)


def _dumps_model_class(model_cls: type[BaseModel]):
    d = {name: _get_attrs_tree(field) for name, field in model_cls.model_fields.items()}
    return json.dumps(d, indent=1)


@pytest.fixture
def create_settings_class() -> Callable[[str], type[BaseCustomSettings]]:
    def _create_cls(class_name: str) -> type[BaseCustomSettings]:
        class S(BaseCustomSettings):
            S_VALUE: int

        class M1(BaseCustomSettings):
            VALUE: S
            VALUE_DEFAULT: S = S(S_VALUE=42)
            # VALUE_CONFUSING: S = None  # type: ignore

            VALUE_NULLABLE_REQUIRED: S | None = ...  # type: ignore

            VALUE_NULLABLE_DEFAULT_VALUE: S | None = S(S_VALUE=42)
            VALUE_NULLABLE_DEFAULT_NULL: S | None = None

            VALUE_NULLABLE_DEFAULT_ENV: S | None = Field(
                json_schema_extra={"auto_default_from_env": True}
            )
            VALUE_DEFAULT_ENV: S = Field(
                json_schema_extra={"auto_default_from_env": True}
            )

        class M2(BaseCustomSettings):
            #
            #  Using nullable fields for subsettings, allows us to easily
            #  mark a module as enabled/disabled
            #

            # defaults disabled but only explicit enabled
            VALUE_NULLABLE_DEFAULT_NULL: S | None = None

            # defaults enabled but if not exists, it disables
            VALUE_NULLABLE_DEFAULT_ENV: S | None = Field(
                json_schema_extra={"auto_default_from_env": True}
            )

            # cannot be disabled
            VALUE_DEFAULT_ENV: S = Field(
                json_schema_extra={"auto_default_from_env": True}
            )

        # Changed in version 3.7: Dictionary order is guaranteed to be insertion order
        _classes = {"M1": M1, "M2": M2, "S": S}
        return _classes.get(class_name) or list(_classes.values())

    return _create_cls


def test_create_settings_class(
    create_settings_class: Callable[[str], type[BaseCustomSettings]]
):
    M = create_settings_class("M1")

    # DEV: Path("M1.ignore.json").write_text(dumps_model_class(M))

    assert M.model_fields["VALUE_NULLABLE_DEFAULT_ENV"].default_factory

    assert M.model_fields["VALUE_NULLABLE_DEFAULT_ENV"].get_default() is None

    assert M.model_fields["VALUE_DEFAULT_ENV"].default_factory

    with pytest.raises(DefaultFromEnvFactoryError):
        M.model_fields["VALUE_DEFAULT_ENV"].get_default(call_default_factory=True)


def test_create_settings_class_with_environment(
    monkeypatch: pytest.MonkeyPatch,
    create_settings_class: Callable[[str], type[BaseCustomSettings]],
):
    # create class within one context
    SettingsClass = create_settings_class("M1")

    with monkeypatch.context() as patch:
        # allows DEFAULT_ENV to be implemented
        patch.setenv("S_VALUE", "1")

        # sets required
        patch.setenv("VALUE", S2)

        # WARNING: patch.setenv("VALUE_NULLABLE_REQUIRED", None)
        # leads to E   pydantic.env_settings.SettingsError: error parsing JSON for "value_nullable_required"
        # because type(M.VALUE_NULLABLE_REQUIRED) is S that is a model and settings try to json.decode from it
        # TODO: So far, i only manage to null it setting VALUE_NULLABLE_REQUIRED=None in the constructor
        # FIXME: if set to {} -> it returns S1 ???
        patch.setenv("VALUE_NULLABLE_REQUIRED", S3)

        _print_defaults(SettingsClass)

        instance = SettingsClass()

        print(instance.model_dump_json(indent=2))

        # checks
        assert instance.model_dump(exclude_unset=True) == {
            "VALUE": {"S_VALUE": 2},
            "VALUE_NULLABLE_REQUIRED": {"S_VALUE": 3},
        }

        assert instance.model_dump() == {
            "VALUE": {"S_VALUE": 2},
            "VALUE_DEFAULT": {"S_VALUE": 42},
            # "VALUE_CONFUSING": None,
            "VALUE_NULLABLE_REQUIRED": {"S_VALUE": 3},
            "VALUE_NULLABLE_DEFAULT_VALUE": {"S_VALUE": 42},
            "VALUE_NULLABLE_DEFAULT_NULL": None,
            "VALUE_NULLABLE_DEFAULT_ENV": {"S_VALUE": 1},
            "VALUE_DEFAULT_ENV": {"S_VALUE": 1},
        }


def test_create_settings_class_without_environ_fails(
    create_settings_class: Callable[[str], type[BaseCustomSettings]],
):
    # now defining S_VALUE
    M2_outside_context = create_settings_class("M2")

    with pytest.raises(DefaultFromEnvFactoryError) as err_info:
        M2_outside_context.create_from_envs()

    assert err_info.value.errors[0] == {
        "input": {},
        "loc": ("S_VALUE",),
        "msg": "Field required",
        "type": "missing",
        "url": "https://errors.pydantic.dev/2.9/v/missing",
    }


def test_create_settings_class_with_environ_passes(
    monkeypatch: pytest.MonkeyPatch,
    create_settings_class: Callable[[str], type[BaseCustomSettings]],
):
    # now defining S_VALUE
    with monkeypatch.context() as patch:
        patch.setenv("S_VALUE", "123")

        M2_inside_context = create_settings_class("M2")
        print(_dumps_model_class(M2_inside_context))

        instance = M2_inside_context.create_from_envs()
        assert instance == M2_inside_context(
            VALUE_NULLABLE_DEFAULT_NULL=None,
            VALUE_NULLABLE_DEFAULT_ENV={"S_VALUE": 123},
            VALUE_DEFAULT_ENV={"S_VALUE": 123},
        )


def test_auto_default_to_none_logs_a_warning(
    create_settings_class: Callable[[str], type[BaseCustomSettings]],
    mocker: MockerFixture,
):
    logger_warn = mocker.spy(settings_library.base._logger, "warning")  # noqa: SLF001

    S = create_settings_class("S")

    class SettingsClass(BaseCustomSettings):
        VALUE_NULLABLE_DEFAULT_NULL: S | None = None
        VALUE_NULLABLE_DEFAULT_ENV: S | None = Field(
            json_schema_extra={"auto_default_from_env": True},
        )

    instance = SettingsClass.create_from_envs()
    assert instance.VALUE_NULLABLE_DEFAULT_NULL is None
    assert instance.VALUE_NULLABLE_DEFAULT_ENV is None

    # Defaulting to None also logs a warning
    assert logger_warn.call_count == 1
    assert (
        _AUTO_DEFAULT_FACTORY_RESOLVES_TO_NONE_FSTRING.format(
            field_name="VALUE_NULLABLE_DEFAULT_ENV"
        )
        in logger_warn.call_args[0][0]
    )


def test_auto_default_to_not_none(
    monkeypatch: pytest.MonkeyPatch,
    create_settings_class: Callable[[str], type[BaseCustomSettings]],
):
    with monkeypatch.context() as patch:
        patch.setenv("S_VALUE", "123")

        S = create_settings_class("S")

        class SettingsClass(BaseCustomSettings):
            VALUE_NULLABLE_DEFAULT_NULL: S | None = None
            VALUE_NULLABLE_DEFAULT_ENV: S | None = Field(
                json_schema_extra={"auto_default_from_env": True},
            )

        instance = SettingsClass.create_from_envs()
        assert instance.VALUE_NULLABLE_DEFAULT_NULL is None
        assert S(S_VALUE=123) == instance.VALUE_NULLABLE_DEFAULT_ENV


def test_how_settings_parse_null_environs(monkeypatch: pytest.MonkeyPatch):
    #
    # We were wondering how nullable fields (i.e. those marked as Optional[.]) can
    # be defined in the envfile. Here we test different options
    #

    envs = setenvs_from_envfile(
        monkeypatch,
        """
    VALUE_TO_NOTHING=
    INT_VALUE_TO_NOTHING=
    VALUE_TO_WORD_NULL=null
    VALUE_TO_WORD_NONE=None
    VALUE_TO_ZERO=0
    INT_VALUE_TO_ZERO=0
    """,
    )

    print(json.dumps(envs, indent=1))

    assert envs == {
        "VALUE_TO_NOTHING": "",
        "INT_VALUE_TO_NOTHING": "",
        "VALUE_TO_WORD_NULL": "null",
        "VALUE_TO_WORD_NONE": "None",
        "VALUE_TO_ZERO": "0",
        "INT_VALUE_TO_ZERO": "0",
    }

    class SettingsClass(BaseCustomSettings):
        VALUE_TO_NOTHING: str | None
        VALUE_TO_WORD_NULL: str | None
        VALUE_TO_WORD_NONE: str | None
        VALUE_TO_ZERO: str | None

        INT_VALUE_TO_ZERO: int | None

    instance = SettingsClass.create_from_envs()

    assert instance == SettingsClass(
        VALUE_TO_NOTHING="",  # NO
        VALUE_TO_WORD_NULL=None,  # OK!
        VALUE_TO_WORD_NONE=None,  # OK!
        VALUE_TO_ZERO="0",  # NO
        INT_VALUE_TO_ZERO=0,  # NO
    )

    class SettingsClassExt(SettingsClass):
        INT_VALUE_TO_NOTHING: int | None

    with pytest.raises(ValidationError) as err_info:
        SettingsClassExt.create_from_envs()

    error = err_info.value.errors()[0]
    assert error == {
        "input": "",
        "loc": ("INT_VALUE_TO_NOTHING",),
        "msg": "Input should be a valid integer, unable to parse string as an integer",
        "type": "int_parsing",
        "url": "https://errors.pydantic.dev/2.9/v/int_parsing",
    }


def test_issubclass_type_error_with_pydantic_models():
    # There is a problem
    #
    # TypeError: issubclass() arg 1 must be a class
    #
    # SEE https://github.com/pydantic/pydantic/issues/545
    #
    # >> issubclass(dict, BaseSettings)
    # False
    # >> issubclass(dict[str, str], BaseSettings)
    # Traceback (most recent call last):
    # File "<string>", line 1, in <module>
    # File "/home/crespo/.pyenv/versions/3.10.13/lib/python3.10/abc.py", line 123, in __subclasscheck__
    #     return _abc_subclasscheck(cls, subclass)
    # TypeError: issubclass() arg 1 must be a class
    #

    assert not issubclass(dict, BaseSettings)

    # NOTE: this should be fixed by pydantic at some point. When this happens, this test will fail
    with pytest.raises(TypeError):
        issubclass(dict[str, str], BaseSettings)

    # here reproduces the problem with our settings that ANE and PC had
    class SettingsClassThatFailed(BaseCustomSettings):
        FOO: dict[str, str] | None = Field(default=None)

    SettingsClassThatFailed(FOO={})
    assert SettingsClassThatFailed(FOO=None) == SettingsClassThatFailed()


def test_upgrade_failure_to_pydantic_settings_2_6(
    mock_env_devel_environment: EnvVarsDict,
):
    class ProblematicSettings(BaseCustomSettings):
        WEBSERVER_EMAIL: SMTPSettings | None = Field(
            json_schema_extra={"auto_default_from_env": True}
        )

        model_config = SettingsConfigDict(nested_model_default_partial_update=True)

    settings = ProblematicSettings()
    assert settings.WEBSERVER_EMAIL is not None
