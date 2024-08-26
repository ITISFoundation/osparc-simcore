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
from pydantic import BaseModel, BaseSettings, ValidationError
from pydantic.fields import Field
from pytest_mock import MockerFixture
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_envfile
from settings_library.base import (
    _DEFAULTS_TO_NONE_MSG,
    BaseCustomSettings,
    DefaultFromEnvFactoryError,
)

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
    for field in model_cls.__fields__.values():
        print(field.name, ":", end="")
        try:
            default = field.get_default()
            print(default, type(default))
        except ValidationError as err:
            print(err)


def _dumps_model_class(model_cls: type[BaseModel]):
    d = {field.name: _get_attrs_tree(field) for field in model_cls.__fields__.values()}
    return json.dumps(d, indent=1)


@pytest.fixture
def create_settings_class() -> Callable[[str], type[BaseCustomSettings]]:
    def _create_cls(class_name: str) -> type[BaseCustomSettings]:
        class S(BaseCustomSettings):
            S_VALUE: int

        class M1(BaseCustomSettings):
            VALUE: S
            VALUE_DEFAULT: S = S(S_VALUE=42)
            VALUE_CONFUSING: S = None  # type: ignore

            VALUE_NULLABLE_REQUIRED: S | None = ...  # type: ignore
            VALUE_NULLABLE_OPTIONAL: S | None

            VALUE_NULLABLE_DEFAULT_VALUE: S | None = S(S_VALUE=42)
            VALUE_NULLABLE_DEFAULT_NULL: S | None = None

            VALUE_NULLABLE_DEFAULT_ENV: S | None = Field(auto_default_from_env=True)
            VALUE_DEFAULT_ENV: S = Field(auto_default_from_env=True)

        class M2(BaseCustomSettings):
            #
            #  Using nullable fields for subsettings, allows us to easily
            #  mark a module as enabled/disabled
            #

            # defaults disabled but only explicit enabled
            VALUE_NULLABLE_DEFAULT_NULL: S | None = None

            # defaults enabled but if not exists, it disables
            VALUE_NULLABLE_DEFAULT_ENV: S | None = Field(auto_default_from_env=True)

            # cannot be disabled
            VALUE_DEFAULT_ENV: S = Field(auto_default_from_env=True)

        # Changed in version 3.7: Dictionary order is guaranteed to be insertion order
        _classes = {"M1": M1, "M2": M2, "S": S}
        return _classes.get(class_name) or list(_classes.values())

    return _create_cls


def test_create_settings_class(
    create_settings_class: Callable[[str], type[BaseCustomSettings]]
):
    M = create_settings_class("M1")

    # DEV: Path("M1.ignore.json").write_text(dumps_model_class(M))

    assert M.__fields__["VALUE_NULLABLE_DEFAULT_ENV"].default_factory

    assert M.__fields__["VALUE_NULLABLE_DEFAULT_ENV"].get_default() is None

    assert M.__fields__["VALUE_DEFAULT_ENV"].default_factory

    with pytest.raises(DefaultFromEnvFactoryError):
        M.__fields__["VALUE_DEFAULT_ENV"].get_default()


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

        print(instance.json(indent=2))

        # checks
        assert instance.dict(exclude_unset=True) == {
            "VALUE": {"S_VALUE": 2},
            "VALUE_NULLABLE_REQUIRED": {"S_VALUE": 3},
        }

        assert instance.dict() == {
            "VALUE": {"S_VALUE": 2},
            "VALUE_DEFAULT": {"S_VALUE": 42},
            "VALUE_CONFUSING": None,
            "VALUE_NULLABLE_REQUIRED": {"S_VALUE": 3},
            "VALUE_NULLABLE_OPTIONAL": None,
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

    with pytest.raises(ValidationError) as err_info:
        M2_outside_context.create_from_envs()

    assert err_info.value.errors()[0] == {
        "loc": ("VALUE_DEFAULT_ENV", "S_VALUE"),
        "msg": "field required",
        "type": "value_error.missing",
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
        VALUE_NULLABLE_DEFAULT_ENV: S | None = Field(auto_default_from_env=True)

    instance = SettingsClass.create_from_envs()
    assert instance.VALUE_NULLABLE_DEFAULT_NULL is None
    assert instance.VALUE_NULLABLE_DEFAULT_ENV is None

    # Defaulting to None also logs a warning
    assert logger_warn.call_count == 1
    assert _DEFAULTS_TO_NONE_MSG in logger_warn.call_args[0][0]


def test_auto_default_to_not_none(
    monkeypatch: pytest.MonkeyPatch,
    create_settings_class: Callable[[str], type[BaseCustomSettings]],
):
    with monkeypatch.context() as patch:
        patch.setenv("S_VALUE", "123")

        S = create_settings_class("S")

        class SettingsClass(BaseCustomSettings):
            VALUE_NULLABLE_DEFAULT_NULL: S | None = None
            VALUE_NULLABLE_DEFAULT_ENV: S | None = Field(auto_default_from_env=True)

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
        "loc": ("INT_VALUE_TO_NOTHING",),
        "msg": "value is not a valid integer",
        "type": "type_error.integer",
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
