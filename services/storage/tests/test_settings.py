# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
import logging

from simcore_service_storage.settings import ApplicationSettings


def test_loading_env_devel_in_settings(project_env_devel_environment):
    settings = ApplicationSettings.create_from_environ()
    print("captured settings: \n", settings.json(indent=2))

    assert settings.logging_level == logging.DEBUG
    assert settings.postgres.dsn == "postgresql://test:secret@localhost:5432/testdb"
