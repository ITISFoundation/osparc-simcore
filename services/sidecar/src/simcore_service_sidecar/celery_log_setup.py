""" setup logging formatters to fit logspout's multiline pattern "^(ERROR|WARNING|INFO|DEBUG|CRITICAL)[:]"

    NOTE: import to connect signals!

    SEE https://github.com/ITISFoundation/osparc-ops/blob/master/services/graylog/docker-compose.yml#L113
"""
# NOTES:
#  https://docs.celeryproject.org/en/latest/userguide/signals.html#setup-logging
#  https://www.distributedpython.com/2018/08/28/celery-logging/
#  https://www.distributedpython.com/2018/11/06/celery-task-logger-format/
import logging

from celery.app.log import TaskFormatter
from celery.signals import after_setup_logger, after_setup_task_logger
from celery.utils.log import get_task_logger


@after_setup_logger.connect
def setup_loggers(logger, *_args, **_kwargs):
    """ Customizes global loggers """
    for handler in logger.handlers:
        handler.setFormatter(
            logging.Formatter(
                "%(levelname)s: [%(asctime)s/%(processName)s] [%(filename)s:%(lineno)d] %(message)s"
            )
        )


@after_setup_task_logger.connect
def setup_task_logger(logger, *_args, **_kwargs):
    """ Customizes task loggers """
    for handler in logger.handlers:
        handler.setFormatter(
            TaskFormatter(
                "%(levelname)s: [%(asctime)s/%(processName)s][%(task_name)s(%(task_id)s)] [%(filename)s:%(lineno)d] %(message)s"
            )
        )


# TODO: configure via command line or config file. Add in config.yaml
log = get_task_logger(__name__)
log.info("Setting up loggers")

__all__ = ["get_task_logger"]
