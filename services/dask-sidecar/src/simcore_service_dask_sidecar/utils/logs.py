from typing import Final

from servicelib.logging_utils import setup_loggers
from servicelib.tracing import TracingConfig

from .._meta import PROJECT_NAME
from ..settings import ApplicationSettings

_NOISY_LOGGERS: Final[tuple[str, ...]] = ("werkzeug",)


def setup_app_logging(settings: ApplicationSettings) -> None:
    tracing_config = TracingConfig.create(
        service_name=PROJECT_NAME,
        tracing_settings=None,  # no tracing for dask sidecar
    )
    setup_loggers(
        log_format_local_dev_enabled=settings.DASK_LOG_FORMAT_LOCAL_DEV_ENABLED,
        logger_filter_mapping=settings.DASK_LOG_FILTER_MAPPING,
        tracing_config=tracing_config,
        log_base_level=settings.log_level,
        noisy_loggers=_NOISY_LOGGERS,
    )
