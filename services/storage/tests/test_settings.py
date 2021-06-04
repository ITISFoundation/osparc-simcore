# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
import logging

from simcore_service_storage.settings import create_settings_class


def test_loading_env_devel_in_settings(project_env_devel_environment):
    ApplicationSettings = create_settings_class()
    settings = ApplicationSettings()
    print("captured settings: \n", settings.json(indent=2))

    assert settings.logging_level == logging.DEBUG
    assert settings.postgres.dsn == "postgresql://test:secret@localhost:5432/testdb"
