import logging

from servicelib.logging_utils import config_all_loggers

from .core import ApplicationSettings
from .modules.task_monitor import TaskMonitor
from .volumes_cleanup import backup_and_remove_volumes


def setup_logger(settings: ApplicationSettings):
    # SEE https://github.com/ITISFoundation/osparc-simcore/issues/3148
    logging.basicConfig(level=settings.LOGLEVEL.value)  # NOSONAR
    logging.root.setLevel(settings.LOGLEVEL.value)
    config_all_loggers()


def create_application() -> TaskMonitor:
    task_monitor = TaskMonitor()

    settings = ApplicationSettings.create_from_envs()
    setup_logger(settings)

    task_monitor.register_job(
        backup_and_remove_volumes,
        settings,
        repeat_interval_s=settings.AGENT_VOLUMES_CLEANUP_INTERVAL_S,
    )

    return task_monitor
