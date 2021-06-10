# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
import logging

from models_library.settings.base import BaseCustomSettings
from pydantic import BaseSettings
from simcore_service_storage.settings import Settings


def test_loading_env_devel_in_settings(project_env_devel_environment):
    settings = Settings.create_from_env()
    print("captured settings: \n", settings.json(indent=2))

    assert settings.logging_level == logging.INFO
    assert (
        settings.STORAGE_POSTGRES.dsn
        == "postgresql://test:secret@localhost:5432/testdb"
    )


def test_all_settings_inherit_from_custom_base(project_env_devel_environment):
    assert issubclass(Settings, BaseCustomSettings)

    def assert_sub_settings_are_customized(settings_cls):
        for name in settings_cls.__fields__:
            field_type = settings_cls.__fields__[name].type_
            if field_type and issubclass(field_type, BaseSettings):
                assert issubclass(
                    field_type, BaseCustomSettings
                ), f"{name} with type {field_type} is not derived from BaseCustomSettings"
                # check fields of sub-settings
                assert_sub_settings_are_customized(field_type)

    # TODO: activate when all settings in packages/models-library/src/models_library/settings are refactored
    # assert_sub_settings_are_customized(Settings)
