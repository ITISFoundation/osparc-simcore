from servicelib.logging_utils import setup_loggers

from ..settings import ApplicationSettings


def setup_app_logging(settings: ApplicationSettings) -> None:
    setup_loggers(
        log_format_local_dev_enabled=settings.DASK_LOG_FORMAT_LOCAL_DEV_ENABLED,
        logger_filter_mapping=settings.DASK_LOG_FILTER_MAPPING,
        tracing_settings=None,  # no tracing for dask sidecar
        log_base_level=settings.log_level,
        noisy_loggers=None,
    )
