# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import importlib
import inspect
from pathlib import Path
from typing import List, Type

import pytest
import settings_library
from pydantic.env_settings import BaseSettings
from settings_library.base import BaseCustomSettings

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


# TESTS -----------------------------------------------------------------------------------
#
# NOTE: Tests below are progressive to understand and validate the construction mechanism
#       implemented in BaseCustomSettings.
#       Pay attention how the defaults of SubSettings are automaticaly captured from env vars
#       at construction time.
#


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
