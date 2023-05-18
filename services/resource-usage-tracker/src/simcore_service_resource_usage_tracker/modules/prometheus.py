import asyncio
import logging
from typing import cast

import requests.exceptions
from fastapi import FastAPI
from prometheus_api_client import PrometheusConnect
from servicelib.logging_utils import log_context
from settings_library.prometheus import PrometheusSettings
from tenacity import retry
from tenacity.before_sleep import before_sleep_log
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_random_exponential

from ..core.errors import ConfigurationError

_logger = logging.getLogger(__name__)


@retry(
    reraise=True,
    stop=stop_after_delay(120),
    wait=wait_random_exponential(max=30),
    before_sleep=before_sleep_log(_logger, logging.WARNING),
    retry=retry_if_exception_type(ConfigurationError),
)
async def _wait_till_prometheus_responsive(client: PrometheusConnect) -> bool:
    try:
        return await asyncio.get_event_loop().run_in_executor(
            None, client.check_prometheus_connection
        )
    except requests.exceptions.ConnectionError as exc:
        raise ConfigurationError(
            msg="Prometheus API client could not be reached. TIP: check configuration"
        ) from exc


def setup(app: FastAPI) -> None:
    async def on_startup() -> None:
        app.state.prometheus_api_client = None
        settings: PrometheusSettings | None = (
            app.state.settings.RESOURCE_USAGE_TRACKER_PROMETHEUS
        )
        if not settings:
            _logger.warning("Prometheus API client is de-activated in the settings")
            return
        with log_context(_logger, logging.INFO, msg="connect with prometheus"):
            client = PrometheusConnect(f"{settings.api_url}")
            if await _wait_till_prometheus_responsive(client) is False:
                raise ConfigurationError(
                    msg="Prometheus API client could be reached but returned value is not expected. TIP: check configuration"
                )
            app.state.prometheus_api_client = client

    async def on_shutdown() -> None:
        if app.state.prometheus_api_client:
            with log_context(_logger, logging.INFO, msg="disconnect with prometheus"):
                del app.state.prometheus_api_client

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


def get_prometheus_api_client(app: FastAPI) -> PrometheusConnect:
    if not app.state.prometheus_api_client:
        raise ConfigurationError(
            msg="Prometheus API client is not available. Please check the configuration."
        )
    return cast(PrometheusConnect, app.state.prometheus_api_client)
