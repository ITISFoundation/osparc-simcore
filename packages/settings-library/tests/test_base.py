# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import importlib
import inspect
import os
from pathlib import Path
from typing import Dict

import pytest
import settings_library
from pydantic import ValidationError
from pydantic.env_settings import BaseSettings
from settings_library.base import BaseCustomSettings


@pytest.mark.parametrize("env_file", (".env-sample", ".env-fails"))
def test_settigs_with_modules_settings(
    env_file: str, mock_environment: Dict, mocks_folder: Path, settings_cls
):

    assert all(
        os.environ[env_name] == env_value
        for env_name, env_value in mock_environment.items()
    )

    if "fail" in env_file:
        with pytest.raises(ValidationError):
            settings = settings_cls.create_from_envs()
    else:
        settings = settings_cls.create_from_envs()
        assert settings.APP_PORT == int(mock_environment["APP_PORT"])

        assert settings.APP_POSTGRES


def _get_all_settings_classes():

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


@pytest.mark.parametrize(
    "settings_cls", _get_all_settings_classes(), ids=lambda cls: cls.__name__
)
def test_settings_class_policies(settings_cls):
    # must inherit
    assert issubclass(settings_cls, BaseCustomSettings)

    # all fields UPPER
    assert all(key == key.upper() for key in settings_cls.__fields__.keys())
