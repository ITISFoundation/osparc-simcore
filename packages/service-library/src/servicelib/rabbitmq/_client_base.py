import asyncio
import logging
from abc import abstractmethod
from dataclasses import dataclass
from typing import Any, Final

import aio_pika
import aiormq
from servicelib.logging_utils import log_catch
from settings_library.rabbit import RabbitSettings

_DEFAULT_RABBITMQ_SERVER_HEARTBEAT_S: Final[int] = 60

_logger = logging.getLogger(__name__)


@dataclass
class RabbitMQClientBase:
    client_name: str
    settings: RabbitSettings
    heartbeat: int = _DEFAULT_RABBITMQ_SERVER_HEARTBEAT_S

    _healthy_state: bool = True

    def _connection_close_callback(
        self,
        sender: Any,  # pylint: disable=unused-argument
        exc: BaseException | None,
    ) -> None:
        if exc:
            if isinstance(exc, asyncio.CancelledError):
                _logger.info("Rabbit connection cancelled")
            elif isinstance(exc, aiormq.exceptions.ConnectionClosed):
                _logger.info("Rabbit connection closed: %s", exc)
            else:
                _logger.error(
                    "Rabbit connection closed with exception from %s:%s",
                    type(exc),
                    exc,
                )
                self._healthy_state = False

    def _channel_close_callback(
        self,
        sender: Any,  # pylint: disable=unused-argument  # noqa: ARG002
        exc: BaseException | None,
    ) -> None:
        if exc:
            if isinstance(exc, asyncio.CancelledError):
                _logger.info("Rabbit channel cancelled")
            elif isinstance(exc, aiormq.exceptions.ChannelClosed):
                _logger.info("Rabbit channel closed")
            else:
                _logger.error(
                    "Rabbit channel closed with exception from %s:%s",
                    type(exc),
                    exc,
                )
                self._healthy_state = False

    @property
    def healthy(self) -> bool:
        return self._healthy_state

    async def ping(self) -> bool:
        with log_catch(_logger, reraise=False):
            async with await aio_pika.connect(self.settings.dsn, timeout=1):
                ...
            return True
        return False  # type: ignore[unreachable]

    @abstractmethod
    async def close(self) -> None: ...
