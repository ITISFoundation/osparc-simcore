import asyncio
import logging
import time
from abc import abstractmethod
from dataclasses import dataclass, field
from typing import Any, Final

import aio_pika
import aiormq
from common_library.logging.logging_errors import create_troubleshooting_log_kwargs
from settings_library.rabbit import RabbitSettings

from ..logging_utils import log_catch

_DEFAULT_RABBITMQ_SERVER_HEARTBEAT_S: Final[int] = 60

# How long a disconnect is tolerated (e.g. AWS MQ maintenance restarts) before
# `healthy` reports False. Avoids flapping unhealthy for brief, self-healing
# reconnects handled transparently by aio_pika's RobustConnection.
_DEFAULT_HEALTH_GRACE_PERIOD_S: Final[float] = 10

_logger = logging.getLogger(__name__)

# Constant for RabbitMQ maintenance mode message
# This message is specific to Amazon MQ for RabbitMQ and occurs during scheduled maintenance windows.
# Reference: https://docs.aws.amazon.com/amazon-mq/latest/developer-guide/maintaining-brokers.html#rabbitmq-broker-architecture-cluster
# During maintenance, Amazon MQ restarts a broker node. For cluster deployments, implement connection retry logic.
_AWS_MAINTENANCE_MODE_MESSAGE: Final[str] = "Node was put into maintenance mode"


@dataclass
class RabbitMQClientBase:
    client_name: str
    settings: RabbitSettings
    heartbeat: int = _DEFAULT_RABBITMQ_SERVER_HEARTBEAT_S
    grace_period_s: float = _DEFAULT_HEALTH_GRACE_PERIOD_S

    _healthy_state: bool = True
    _unhealthy_since: float | None = field(default=None, init=False, repr=False)

    def _mark_unhealthy(self) -> None:
        self._healthy_state = False
        if self._unhealthy_since is None:
            self._unhealthy_since = time.monotonic()

    def _mark_healthy(self) -> None:
        self._healthy_state = True
        self._unhealthy_since = None

    def _connection_close_callback(
        self,
        sender: Any,  # pylint: disable=unused-argument
        exc: BaseException | None,
    ) -> None:
        if exc:
            if isinstance(exc, asyncio.CancelledError | aiormq.exceptions.ConnectionClosed):
                _logger.info(
                    **create_troubleshooting_log_kwargs(
                        "RabbitMQ connection closed",
                        error=exc,
                        error_context={"sender": sender},
                    )
                )
            else:
                _logger.error(
                    **create_troubleshooting_log_kwargs(
                        "RabbitMQ connection closed with unexpected error",
                        error=exc,
                        error_context={"sender": sender},
                    )
                )
            self._mark_unhealthy()

    def _channel_close_callback(
        self,
        sender: Any,
        exc: BaseException | None,
    ) -> None:
        if exc:
            if isinstance(exc, asyncio.CancelledError | aiormq.exceptions.ChannelClosed) or (
                isinstance(exc, aiormq.exceptions.ConnectionClosed) and _AWS_MAINTENANCE_MODE_MESSAGE in f"{exc}"
            ):
                _logger.info(
                    **create_troubleshooting_log_kwargs(
                        "RabbitMQ channel closed gracefully (maintenance mode)",
                        error=exc,
                        error_context={"sender": sender},
                    )
                )
            else:
                _logger.error(
                    **create_troubleshooting_log_kwargs(
                        "RabbitMQ channel closed with unexpected error",
                        error=exc,
                        error_context={"sender": sender},
                    )
                )
            self._mark_unhealthy()

    def _connection_reconnect_callback(
        self,
        _connection: Any = None,
    ) -> None:
        _logger.info(
            "RabbitMQ (re)connected (%s): restoring healthy state",
            self.client_name,
        )
        self._mark_healthy()

    @property
    def healthy(self) -> bool:
        if self._healthy_state:
            return True
        if self._unhealthy_since is None:
            return False
        return (time.monotonic() - self._unhealthy_since) < self.grace_period_s

    async def ping(self) -> bool:
        with log_catch(_logger, reraise=False):
            async with await aio_pika.connect(self.settings.dsn, timeout=1):
                ...
            return True
        return False

    @abstractmethod
    async def close(self) -> None: ...
