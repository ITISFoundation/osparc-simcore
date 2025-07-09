"""Main application to be deployed by uvicorn (or equivalent) server"""

from typing import Final

from fastapi import FastAPI
from servicelib.logging_utils import setup_loggers
from simcore_service_clusters_keeper.core.application import create_app
from simcore_service_clusters_keeper.core.settings import ApplicationSettings

_NOISY_LOGGERS: Final[tuple[str, ...]] = (
    "aiobotocore",
    "aio_pika",
    "aiormq",
    "botocore",
    "werkzeug",
)

the_settings = ApplicationSettings.create_from_envs()
setup_loggers(
    log_format_local_dev_enabled=the_settings.CLUSTERS_KEEPER_LOG_FORMAT_LOCAL_DEV_ENABLED,
    logger_filter_mapping=the_settings.CLUSTERS_KEEPER_LOG_FILTER_MAPPING,
    tracing_settings=the_settings.CLUSTERS_KEEPER_TRACING,
    log_base_level=the_settings.log_level,
    noisy_loggers=_NOISY_LOGGERS,
)

# SINGLETON FastAPI app
the_app: FastAPI = create_app(the_settings)
