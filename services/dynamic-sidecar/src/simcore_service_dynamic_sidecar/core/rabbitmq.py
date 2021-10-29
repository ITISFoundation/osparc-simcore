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
    def __init__(self, app: FastAPI) -> None:
        settings: DynamicSidecarSettings = app.state.settings

        assert settings.RABBIT_SETTINGS  # nosec
        self._rabbit_settings: RabbitSettings = settings.RABBIT_SETTINGS
        self._user_id: UserID = settings.DY_SIDECAR_USER_ID
        self._project_id: ProjectID = settings.DY_SIDECAR_PROJECT_ID
        self._node_id: NodeID = settings.DY_SIDECAR_NODE_ID

        self._connection: Optional[aio_pika.Connection] = None
        self._channel: Optional[aio_pika.Channel] = None
        self._logs_exchange: Optional[aio_pika.Exchange] = None

    async def connect(self) -> None:
        url = self._rabbit_settings.dsn
        log.debug("Connecting to %s", url)
        await _wait_till_rabbit_responsive(url)

        # NOTE: to show the connection name in the rabbitMQ UI see there [https://www.bountysource.com/issues/89342433-setting-custom-connection-name-via-client_properties-doesn-t-work-when-connecting-using-an-amqp-url]
        hostname = socket.gethostname()
        self._connection = await aio_pika.connect(
            url + f"?name={__name__}_{id(hostname)}",
            client_properties={
                "connection_name": f"dynamic-sidecar_{self._node_id} {hostname}"
            },
        )
        self._connection.add_close_callback(_close_callback)

        log.debug("Creating channel")
        self._channel = await self._connection.channel(publisher_confirms=False)
        self._channel.add_close_callback(_channel_close_callback)

        log.debug("Declaring %s exchange", self._rabbit_settings.RABBIT_CHANNELS["log"])
        self._logs_exchange = await self._channel.declare_exchange(
            self._rabbit_settings.RABBIT_CHANNELS["log"], aio_pika.ExchangeType.FANOUT
        )

    async def close(self) -> None:
        if self._channel is not None:
            await self._channel.close()
        if self._connection is not None:
            await self._connection.close()

    async def _post_message(self, data: Dict[str, Union[str, Any]]) -> None:
        assert self._logs_exchange  # nosec

        # TODO: accumulate messages by `Channel` name and push them forward
        # in at set intervals, ensures webserver will not get overwhelmed
        await self._logs_exchange.publish(
            aio_pika.Message(body=json.dumps(data).encode()), routing_key=""
        )

    async def post_log_message(self, log_msg: Union[str, List[str]]) -> None:
        await self._post_message(
            data={
                "Channel": "Log",
                "Node": f"{self._node_id}",
                "user_id": f"{self._user_id}",
                "project_id": f"{self._project_id}",
                "Messages": log_msg if isinstance(log_msg, list) else [log_msg],
            },
        )


def setup_rabbitmq(app: FastAPI) -> None:
    async def on_startup() -> None:
        app.state.rabbitmq = RabbitMQ(app)

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
