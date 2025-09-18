import asyncio
import logging
from abc import abstractmethod
from dataclasses import dataclass
from typing import Any, Final

import aio_pika
import aiormq
from common_library.logging.logging_errors import create_troubleshooting_log_kwargs
from settings_library.rabbit import RabbitSettings

from ..logging_utils import log_catch

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
            if isinstance(
                exc, asyncio.CancelledError | aiormq.exceptions.ConnectionClosed
            ):
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
                self._healthy_state = False

    def _channel_close_callback(
        self,
        sender: Any,
        exc: BaseException | None,
    ) -> None:
        if exc:
            if isinstance(
                exc, asyncio.CancelledError | aiormq.exceptions.ChannelClosed
            ):
                _logger.info(
                    **create_troubleshooting_log_kwargs(
                        "RabbitMQ channel closed",
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
                self._healthy_state = False

    @property
    def healthy(self) -> bool:
        return self._healthy_state

    async def ping(self) -> bool:
        with log_catch(_logger, reraise=False):
            async with await aio_pika.connect(self.settings.dsn, timeout=1):
                ...
            return True
        return False

    @abstractmethod
    async def close(self) -> None: ...
