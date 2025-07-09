import logging

from servicelib.logging_utils import setup_loggers

from ..settings import ApplicationSettings


def setup_app_logging(settings: ApplicationSettings) -> None:
    # set up logging
    logging.basicConfig(level=settings.DASK_SIDECAR_LOGLEVEL.value)
    logging.root.setLevel(level=settings.DASK_SIDECAR_LOGLEVEL.value)
    # NOTE: Dask attaches a StreamHandler to the logger in distributed
    # removing them solves dual propagation of logs
    for handler in logging.getLogger("distributed").handlers:
        logging.getLogger("distributed").removeHandler(handler)
    setup_loggers(
        log_format_local_dev_enabled=settings.DASK_LOG_FORMAT_LOCAL_DEV_ENABLED,
        logger_filter_mapping=settings.DASK_LOG_FILTER_MAPPING,
        tracing_settings=None,  # no tracing for dask sidecar
    )
