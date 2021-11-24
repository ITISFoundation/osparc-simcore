from __future__ import annotations

import asyncio
import logging
import os
import socket
from asyncio import CancelledError, Queue, Task
from typing import Any, Dict, List, Optional, Union

import aio_pika
from fastapi import FastAPI
from models_library.projects import ProjectID
from models_library.projects_nodes import NodeID
from models_library.rabbitmq_messages import (
    EventRabbitMessage,
    LoggerRabbitMessage,
    RabbitEventMessageType,
)
from models_library.users import UserID
from servicelib.rabbitmq_utils import RabbitMQRetryPolicyUponInitialization
from settings_library.rabbit import RabbitSettings
from tenacity._asyncio import AsyncRetrying

from ..core.settings import DynamicSidecarSettings

log = logging.getLogger(__file__)

# limit logs displayed
logging.getLogger("aio_pika").setLevel(logging.WARNING)

SLEEP_BETWEEN_SENDS: float = 1.0


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


async def _wait_till_rabbit_responsive(url: str) -> None:
    async for attempt in AsyncRetrying(
        **RabbitMQRetryPolicyUponInitialization().kwargs
    ):
        with attempt:
            connection = await aio_pika.connect(url, timeout=1.0)
            await connection.close()


class RabbitMQ:  # pylint: disable = too-many-instance-attributes
    CHANNEL_LOG = "logger"

    def __init__(self, app: FastAPI, max_messages_to_send: int = 100) -> None:
        settings: DynamicSidecarSettings = app.state.settings

        assert settings.RABBIT_SETTINGS  # nosec
        self._rabbit_settings: RabbitSettings = settings.RABBIT_SETTINGS
        self._user_id: UserID = settings.DY_SIDECAR_USER_ID
        self._project_id: ProjectID = settings.DY_SIDECAR_PROJECT_ID
        self._node_id: NodeID = settings.DY_SIDECAR_NODE_ID

        self._connection: Optional[aio_pika.Connection] = None
        self._channel: Optional[aio_pika.Channel] = None
        self._logs_exchange: Optional[aio_pika.Exchange] = None
        self._events_exchange: Optional[aio_pika.Exchange] = None

        self.max_messages_to_send: int = max_messages_to_send
        # pylint: disable=unsubscriptable-object
        self._channel_queues: Dict[str, Queue[str]] = {}
        self._keep_running: bool = True
        self._queues_worker: Optional[Task[Any]] = None

    async def connect(self) -> None:
        url = self._rabbit_settings.dsn
        log.debug("Connecting to %s", url)
        await _wait_till_rabbit_responsive(url)

        # NOTE: to show the connection name in the rabbitMQ UI see there [https://www.bountysource.com/issues/89342433-setting-custom-connection-name-via-client_properties-doesn-t-work-when-connecting-using-an-amqp-url]
        hostname = socket.gethostname()
        self._connection = await aio_pika.connect(
            url + f"?name={__name__}_{id(hostname)}_{os.getpid()}",
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
        self._channel_queues[self.CHANNEL_LOG] = Queue()

        log.debug(
            "Declaring %s exchange", self._rabbit_settings.RABBIT_CHANNELS["events"]
        )
        self._events_exchange = await self._channel.declare_exchange(
            self._rabbit_settings.RABBIT_CHANNELS["events"],
            aio_pika.ExchangeType.FANOUT,
        )

        # start background worker to dispatch messages
        self._keep_running = True
        self._queues_worker = asyncio.create_task(self._dispatch_messages_worker())

    async def _dispatch_messages_worker(self) -> None:
        while self._keep_running:
            for queue in self._channel_queues.values():
                # in order to avoid blocking when dispatching messages
                # it is important to fetch them an at most the existing
                # messages in the queue
                messages_to_fetch = min(self.max_messages_to_send, queue.qsize())
                messages = [await queue.get() for _ in range(messages_to_fetch)]

                # currently there are no messages do not broardcast
                # an empty payload
                if not messages:
                    continue
                await self._publish_messages(messages)

            await asyncio.sleep(SLEEP_BETWEEN_SENDS)

    async def _publish_messages(self, messages: List[str]) -> None:
        data = LoggerRabbitMessage(
            node_id=self._node_id,
            user_id=self._user_id,
            project_id=self._project_id,
            messages=messages,
        )

        assert self._logs_exchange  # nosec
        await self._logs_exchange.publish(
            aio_pika.Message(body=data.json().encode()), routing_key=""
        )

    async def _publish_event(self, action: RabbitEventMessageType) -> None:
        data = EventRabbitMessage(
            node_id=self._node_id,
            user_id=self._user_id,
            project_id=self._project_id,
            action=action,
        )
        assert self._events_exchange  # nosec
        await self._events_exchange.publish(
            aio_pika.Message(body=data.json().encode()), routing_key=""
        )

    async def send_event_reload_iframe(self) -> None:
        await self._publish_event(action=RabbitEventMessageType.RELOAD_IFRAME)

    async def post_log_message(self, log_msg: Union[str, List[str]]) -> None:
        if isinstance(log_msg, str):
            log_msg = [log_msg]

        for message in log_msg:
            await self._channel_queues[self.CHANNEL_LOG].put(message)

    async def close(self) -> None:
        if self._channel is not None:
            await self._channel.close()
        if self._connection is not None:
            await self._connection.close()

        # wait for queues to be empty before sending the last messages
        self._keep_running = False
        if self._queues_worker is not None:
            await self._queues_worker


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
