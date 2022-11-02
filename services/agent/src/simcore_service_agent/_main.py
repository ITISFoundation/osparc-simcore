import logging

from servicelib.logging_utils import config_all_loggers

from ._app import Application
from ._settings import ApplicationSettings
from .info import info_exposer
from .volumes_cleanup import backup_and_remove_volumes


def setup_logger(settings: ApplicationSettings):
    # SEE https://github.com/ITISFoundation/osparc-simcore/issues/3148
    logging.basicConfig(level=settings.LOGLEVEL.value)  # NOSONAR
    logging.root.setLevel(settings.LOGLEVEL.value)
    config_all_loggers()


def create_application() -> Application:
    app = Application()

    settings = ApplicationSettings.create_from_envs()
    setup_logger(settings)

    app.add_job(
        backup_and_remove_volumes,
        settings,
        repeat_interval_s=settings.AGENT_INTERVAL_VOLUMES_CLEANUP_S,
    )
    app.add_job(info_exposer, app)

    return app
