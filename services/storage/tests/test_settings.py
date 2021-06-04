# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
import logging

from simcore_service_storage.settings import Settings


def test_loading_env_devel_in_settings(project_env_devel_environment):
    settings = Settings.create_from_env()
    print("captured settings: \n", settings.json(indent=2))

    assert settings.logging_level == logging.DEBUG
    assert settings.postgres.dsn == "postgresql://test:secret@localhost:5432/testdb"
