"""Main application to be deployed in for example uvicorn."""

from servicelib.logging_utils import setup_loggers
from simcore_service_storage.core.application import create_app
from simcore_service_storage.core.settings import ApplicationSettings

_settings = ApplicationSettings.create_from_envs()

setup_loggers(
    log_format_local_dev_enabled=_settings.STORAGE_LOG_FORMAT_LOCAL_DEV_ENABLED,
    logger_filter_mapping=_settings.STORAGE_LOG_FILTER_MAPPING,
    tracing_settings=_settings.STORAGE_TRACING,
    log_base_level=_settings.log_level,
    noisy_loggers=None,
)

app = create_app(_settings)
