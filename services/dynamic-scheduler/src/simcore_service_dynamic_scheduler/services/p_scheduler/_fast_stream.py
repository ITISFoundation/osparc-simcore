import logging
from typing import Any, Final, Protocol

from faststream.rabbit import RabbitBroker
from servicelib.fastapi.app_state import SingletonInAppStateMixin
from settings_library.rabbit import RabbitSettings

_DEFAULT_LOG_LEVEL: Final[int] = logging.INFO

type RoutingKey = str


class MessageHandlerProtocol(Protocol):
    async def __call__(self, message: Any) -> None: ...


class FastStreamManager(SingletonInAppStateMixin):
    app_state_name: str = "p_scheduler_fast_stream_manager"

    def __init__(
        self,
        rabbit_settings: RabbitSettings,
        handlers: dict[RoutingKey, MessageHandlerProtocol],
        log_level: int = _DEFAULT_LOG_LEVEL,
    ) -> None:
        self.broker = RabbitBroker(rabbit_settings.dsn, log_level=log_level)
        self._handlers = handlers

    async def _subscie_handler(self, routing_key: str, handler: MessageHandlerProtocol) -> None:
        self.broker.subscriber(routing_key)(handler)

    async def publish(self, message: Any, routing_key: RoutingKey) -> None:
        await self.broker.publish(message, routing_key)

    async def setup(self) -> None:
        for routing_key, handler in self._handlers.items():
            await self._subscie_handler(routing_key, handler)
        await self.broker.start()

    async def shutdown(self) -> None:
        await self.broker.close()
