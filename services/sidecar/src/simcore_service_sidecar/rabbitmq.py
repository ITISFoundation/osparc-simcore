import json
import logging
import socket
from asyncio.futures import CancelledError
from typing import Any, Dict, List, Optional, Union

import aio_pika
import tenacity
from models_library.settings.celery import CeleryConfig
from pydantic import BaseModel  # pylint: disable=no-name-in-module
from servicelib.logging_utils import log_decorator
from servicelib.rabbitmq_utils import RabbitMQRetryPolicyUponInitialization

from . import config

log = logging.getLogger(__file__)


def _close_callback(sender: Any, exc: Optional[BaseException]):
    if exc:
        if isinstance(exc, CancelledError):
            log.info("Rabbit connection was cancelled", exc_info=True)
        else:
            log.error(
                "Rabbit connection closed with exception from %s:",
                sender,
                exc_info=True,
            )
    else:
        log.info("Rabbit connection closed from %s", sender)


def _channel_close_callback(sender: Any, exc: Optional[BaseException]):
    if exc:
        log.error(
            "Rabbit channel closed with exception from %s:", sender, exc_info=True
        )
    else:
        log.info("Rabbit channel closed from %s", sender)


class RabbitMQ(BaseModel):
    celery_config: CeleryConfig = None
    connection: aio_pika.Connection = None
    channel: aio_pika.Channel = None
    logs_exchange: aio_pika.Exchange = None
    instrumentation_exchange: aio_pika.Exchange = None

    class Config:
        # see https://pydantic-docs.helpmanual.io/usage/types/#arbitrary-types-allowed
        arbitrary_types_allowed = True

    @log_decorator(logger=log)
    async def connect(self):
        if not self.celery_config:
            self.celery_config = config.CELERY_CONFIG
        url = self.celery_config.rabbit.dsn
        log.debug("Connecting to %s", url)
        await _wait_till_rabbit_responsive(url)

        # NOTE: to show the connection name in the rabbitMQ UI see there [https://www.bountysource.com/issues/89342433-setting-custom-connection-name-via-client_properties-doesn-t-work-when-connecting-using-an-amqp-url]
        self.connection = await aio_pika.connect(
            url + f"?name={__name__}_{id(socket.gethostname())}",
            client_properties={"connection_name": "sidecar connection"},
        )
        self.connection.add_close_callback(_close_callback)

        log.debug("Creating channel")
        self.channel = await self.connection.channel(publisher_confirms=False)
        self.channel.add_close_callback(_channel_close_callback)

        log.debug("Declaring %s exchange", self.celery_config.rabbit.channels["log"])
        self.logs_exchange = await self.channel.declare_exchange(
            self.celery_config.rabbit.channels["log"], aio_pika.ExchangeType.FANOUT
        )

        log.debug(
            "Declaring %s exchange",
            self.celery_config.rabbit.channels["instrumentation"],
        )
        self.instrumentation_exchange = await self.channel.declare_exchange(
            self.celery_config.rabbit.channels["instrumentation"],
            aio_pika.ExchangeType.FANOUT,
        )

    @log_decorator(logger=log)
    async def close(self):
        await self.channel.close()
        await self.connection.close()

    @log_decorator(logger=log)
    async def _post_message(
        self, exchange: aio_pika.Exchange, data: Dict[str, Union[str, Any]]
    ):
        await exchange.publish(
            aio_pika.Message(body=json.dumps(data).encode()), routing_key=""
        )

    async def post_log_message(
        self,
        user_id: str,
        project_id: str,
        node_id: str,
        log_msg: Union[str, List[str]],
    ):
        await self._post_message(
            self.logs_exchange,
            data={
                "Channel": "Log",
                "Node": node_id,
                "user_id": user_id,
                "project_id": project_id,
                "Messages": log_msg if isinstance(log_msg, list) else [log_msg],
            },
        )

    async def post_progress_message(
        self, user_id: str, project_id: str, node_id: str, progress_msg: str
    ):
        await self._post_message(
            self.logs_exchange,
            data={
                "Channel": "Progress",
                "Node": node_id,
                "user_id": user_id,
                "project_id": project_id,
                "Progress": progress_msg,
            },
        )

    async def post_instrumentation_message(
        self,
        instrumentation_data: Dict,
    ):
        await self._post_message(
            self.instrumentation_exchange,
            data=instrumentation_data,
        )

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()


@tenacity.retry(**RabbitMQRetryPolicyUponInitialization().kwargs)
async def _wait_till_rabbit_responsive(url: str):
    connection = await aio_pika.connect(url)
    await connection.close()
    return True
