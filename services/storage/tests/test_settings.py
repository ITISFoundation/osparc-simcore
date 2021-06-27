# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
import logging

from simcore_service_storage.settings import Settings


def test_loading_env_devel_in_settings(project_env_devel_environment):
    settings = Settings.create_from_envs()
    print("captured settings: \n", settings.json(indent=2))

    assert settings.log_level == logging.INFO
    assert (
        settings.STORAGE_POSTGRES.dsn
        == "postgresql://test:secret@localhost:5432/testdb"
    )
