import json
import logging
import socket
from asyncio import CancelledError
from typing import Any, Dict, List, Optional, Union

import aio_pika
import tenacity
from fastapi import FastAPI
from models_library.projects import ProjectID
from models_library.projects_nodes import NodeID
from models_library.users import UserID
from servicelib.rabbitmq_utils import RabbitMQRetryPolicyUponInitialization
from settings_library.rabbit import RabbitSettings

from ..core.settings import DynamicSidecarSettings

log = logging.getLogger(__file__)


def _close_callback(sender: Any, exc: Optional[BaseException]) -> None:
    if exc:
        if isinstance(exc, CancelledError):
            log.info("Rabbit connection was cancelled", exc_info=True)
        else:
            log.error(
                "Rabbit connection closed with exception from %s:",
                sender,
                exc_info=True,
            )


def _channel_close_callback(sender: Any, exc: Optional[BaseException]) -> None:
    if exc:
        log.error(
            "Rabbit channel closed with exception from %s:", sender, exc_info=True
        )


@tenacity.retry(**RabbitMQRetryPolicyUponInitialization().kwargs)
async def _wait_till_rabbit_responsive(url: str) -> bool:
    connection = await aio_pika.connect(url)
    await connection.close()
    return True


class RabbitMQ:
    def __init__(self, node_id: NodeID, rabbit_settings: RabbitSettings) -> None:
        self.node_id: NodeID = node_id
        self.rabbit_settings: RabbitSettings = rabbit_settings
        self._connection: Optional[aio_pika.Connection] = None
        self._channel: Optional[aio_pika.Channel] = None
        self._logs_exchange: Optional[aio_pika.Exchange] = None

    async def connect(self) -> None:
        url = self.rabbit_settings.dsn
        log.debug("Connecting to %s", url)
        await _wait_till_rabbit_responsive(url)

        # NOTE: to show the connection name in the rabbitMQ UI see there [https://www.bountysource.com/issues/89342433-setting-custom-connection-name-via-client_properties-doesn-t-work-when-connecting-using-an-amqp-url]
        hostname = socket.gethostname()
        self._connection = await aio_pika.connect(
            url + f"?name={__name__}_{id(hostname)}",
            client_properties={
                "connection_name": f"dynamic-sidecar_{self.node_id} {hostname}"
            },
        )
        self._connection.add_close_callback(_close_callback)

        log.debug("Creating channel")
        self._channel = await self._connection.channel(publisher_confirms=False)
        self._channel.add_close_callback(_channel_close_callback)

        log.debug("Declaring %s exchange", self.rabbit_settings.RABBIT_CHANNELS["log"])
        self._logs_exchange = await self._channel.declare_exchange(
            self.rabbit_settings.RABBIT_CHANNELS["log"], aio_pika.ExchangeType.FANOUT
        )

    async def close(self) -> None:
        if self._channel is not None:
            await self._channel.close()
        if self._connection is not None:
            await self._connection.close()

    @staticmethod
    async def _post_message(
        exchange: aio_pika.Exchange, data: Dict[str, Union[str, Any]]
    ) -> None:
        await exchange.publish(
            aio_pika.Message(body=json.dumps(data).encode()), routing_key=""
        )

    async def post_log_message(
        self,
        user_id: UserID,
        project_id: ProjectID,
        node_id: NodeID,
        log_msg: Union[str, List[str]],
    ) -> None:
        await self._post_message(
            self._logs_exchange,
            data={
                "Channel": "Log",
                "Node": f"{node_id}",
                "user_id": f"{user_id}",
                "project_id": f"{project_id}",
                "Messages": log_msg if isinstance(log_msg, list) else [log_msg],
            },
        )


def setup_rabbitmq(app: FastAPI) -> None:
    async def on_startup() -> None:
        settings: DynamicSidecarSettings = app.state.settings

        app.state.rabbitmq = RabbitMQ(
            settings.DY_SIDECAR_NODE_ID, settings.RABBIT_SETTINGS
        )

        log.info("Connecting to rabbitmq")
        await app.state.rabbitmq.connect()
        log.info("Connected to rabbitmq")

    async def on_shutdown() -> None:
        if app.state.background_log_fetcher is None:
            log.warning("No rabbitmq to close")
            return

        await app.state.rabbitmq.close()
        log.info("stopped rabbitmq")

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)
