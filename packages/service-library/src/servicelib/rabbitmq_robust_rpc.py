import asyncio
from typing import Any, Awaitable, Final, Optional
from uuid import uuid4

from aio_pika import (
    MessageProcessError,
    RobustChannel,
    RobustConnection,
    connect_robust,
)
from aio_pika.patterns import RPC
from pydantic import PositiveFloat
from pydantic.errors import PydanticErrorMixin
from settings_library.rabbit import RabbitSettings

_ERROR_PREFIX: Final[str] = "rabbitmq.robust_rpc."


class BaseRPCError(PydanticErrorMixin, RuntimeError):
    ...


class NotStartedError(BaseRPCError):
    code = f"{_ERROR_PREFIX}.not_started"
    msg_template = (
        "{class_name} was not fully initialized, check that start() was called."
    )


class RemoteMethodNotRegisteredError(BaseRPCError):
    code = f"{_ERROR_PREFIX}.remote_not_registered"
    msg_template = (
        "Could not find a remote method named: '{method_name}'. "
        "Message from remote server was returned: {incoming_message}. "
    )


class RPCBase:
    def __init__(self, rabbit_settings: RabbitSettings, channel_name: str) -> None:
        self.channel_name = channel_name
        self.rabbit_settings = rabbit_settings

        self._connection: Optional[RobustConnection] = None
        self._channel: Optional[RobustChannel] = None
        self._rpc: Optional[RPC] = None

    async def start(self) -> None:
        self._connection = await connect_robust(
            self.rabbit_settings.dsn,
            client_properties={"connection_name": self.channel_name},
        )

        self._channel = await self._connection.channel()
        self._rpc = await RPC.create(self._channel)

    async def stop(self) -> None:
        if self._rpc is not None:
            await self._rpc.close()
        if self._channel is not None:
            await self._channel.close()
        if self._connection is not None:
            await self._connection.close()


class RobustRPCClient(RPCBase):
    def __init__(self, rabbit_settings: RabbitSettings) -> None:
        channel_name = f"{RobustRPCClient.__name__}{uuid4()}"
        super().__init__(rabbit_settings, channel_name)

    async def request(
        self, method_name, *, timeout: Optional[PositiveFloat] = 5, **kwargs
    ) -> Any:
        """
        Calls into an already existing handler which was defined refined remotely
        """

        if not self._rpc:
            raise NotStartedError(class_name=self.__class__.__name__)

        try:
            return await asyncio.wait_for(
                self._rpc.call(method_name, kwargs=kwargs), timeout=timeout
            )
        except MessageProcessError as e:
            if e.args[0] == "Message has been returned":
                raise RemoteMethodNotRegisteredError(
                    method_name=method_name, incoming_message=e.args[1]
                ) from e
            raise e


class RobustRPCServer(RPCBase):
    def __init__(self, rabbit_settings: RabbitSettings) -> None:
        channel_name = f"{RobustRPCServer.__name__}{uuid4()}"
        super().__init__(rabbit_settings, channel_name)

    async def register(self, handler: Awaitable) -> None:
        """register an awaitable handler that can be invoked remotely"""

        if self._rpc is None:
            raise NotStartedError(class_name=self.__class__.__name__)

        await self._rpc.register(handler.__name__, handler, auto_delete=True)
