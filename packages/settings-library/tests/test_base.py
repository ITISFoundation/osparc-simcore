# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import json
from pathlib import Path
from typing import Optional

import pytest
from pydantic import ValidationError
from pydantic.fields import Field
from settings_library.base import BaseCustomSettings, DefaultFromEnvFactoryError

# HELPERS --------------------------------------------------------------------
S2 = json.dumps({"S_VALUE": 2})
S3 = json.dumps({"S_VALUE": 3})


def get_attrs_tree(obj):
    # long version of json.dumps({ k:str(getattr(field,k)) for k in ModelField.__slots__ } )
    tree = {}
    for name in obj.__class__.__slots__:
        value = getattr(obj, name)
        if hasattr(value.__class__, "__slots__"):
            tree[name] = get_attrs_tree(value)
        else:
            tree[name] = f"{value}"

    return tree


def print_defaults(model_cls):
    for field in model_cls.__fields__.values():
        print(field.name, ":", end="")
        try:
            default = field.get_default()
            print(default, type(default))
        except ValidationError as err:
            print(err)


def dumps_model_class(model_cls):
    d = {field.name: get_attrs_tree(field) for field in model_cls.__fields__.values()}
    return json.dumps(d, indent=2)


@pytest.fixture
def model_class_factory():
    def _create_model(class_name):
        class S(BaseCustomSettings):
            S_VALUE: int

        class M1(BaseCustomSettings):
            VALUE: S
            VALUE_DEFAULT: S = S(S_VALUE=42)
            VALUE_CONFUSING: S = None  # type: ignore

            VALUE_NULLABLE_REQUIRED: Optional[S] = ...  # type: ignore
            VALUE_NULLABLE_OPTIONAL: Optional[S]

            VALUE_NULLABLE_DEFAULT_VALUE: Optional[S] = S(S_VALUE=42)
            VALUE_NULLABLE_DEFAULT_NULL: Optional[S] = None

            VALUE_NULLABLE_DEFAULT_ENV: Optional[S] = Field(auto_default_from_env=True)
            VALUE_DEFAULT_ENV: S = Field(auto_default_from_env=True)

        class M2(BaseCustomSettings):
            #
            #  Using nullable fields for subsettings, allows us to easily
            #  mark a module as enabled/disabled
            #

            # defaults disabled but only explicit enabled
            VALUE_NULLABLE_DEFAULT_NULL: Optional[S] = None

            # defaults enabled but if not exists, it disables
            VALUE_NULLABLE_DEFAULT_ENV: Optional[S] = Field(auto_default_from_env=True)

            # cannot be disabled
            VALUE_DEFAULT_ENV: S = Field(auto_default_from_env=True)

        # Changed in version 3.7: Dictionary order is guaranteed to be insertion order
        _classes = {"M1": M1, "M2": M2}
        return _classes.get(class_name) or list(_classes.values())

    return _create_model


# TEST ---------------------------------------------------------------


def test_without_envs(model_class_factory):

    M = model_class_factory("M1")

    # DEV: Path("M1.ignore.json").write_text(dumps_model_class(M))

    assert M.__fields__["VALUE_NULLABLE_DEFAULT_ENV"].default_factory

    assert M.__fields__["VALUE_NULLABLE_DEFAULT_ENV"].get_default() == None

    assert M.__fields__["VALUE_DEFAULT_ENV"].default_factory

    with pytest.raises(DefaultFromEnvFactoryError):
        M.__fields__["VALUE_DEFAULT_ENV"].get_default()


def test_with_envs(monkeypatch, model_class_factory):

    M = model_class_factory("M1")

    with monkeypatch.context() as patch:

        # Environment

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

        #
        print_defaults(M)

        obj = M()

        print(obj.json(indent=2))

        # checks
        assert obj.dict(exclude_unset=True) == {
            "VALUE": {"S_VALUE": 2},
            "VALUE_NULLABLE_REQUIRED": {"S_VALUE": 3},
        }

        assert obj.dict() == {
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


def test_2(monkeypatch, model_class_factory):

    M = model_class_factory("M2")
    Path("M2.ignore.json").write_text(dumps_model_class(M))
