import json
import logging
import socket
from asyncio import CancelledError
from typing import Any, Dict, List, Optional, Union

import aio_pika
import tenacity
from models_library.settings.celery import CeleryConfig
from models_library.settings.rabbit import (  # pylint: disable=no-name-in-module
    RabbitDsn,
)
from pydantic import BaseModel, PrivateAttr
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


def _channel_close_callback(sender: Any, exc: Optional[BaseException]):
    if exc:
        log.error(
            "Rabbit channel closed with exception from %s:", sender, exc_info=True
        )


class RabbitMQ(BaseModel):
    celery_config: Optional[CeleryConfig] = None
    _connection: aio_pika.Connection = PrivateAttr()
    _channel: aio_pika.Channel = PrivateAttr()
    _logs_exchange: aio_pika.Exchange = PrivateAttr()
    _instrumentation_exchange: aio_pika.Exchange = PrivateAttr()

    class Config:
        # see https://pydantic-docs.helpmanual.io/usage/types/#arbitrary-types-allowed
        arbitrary_types_allowed = True

    async def connect(self):
        if not self.celery_config:
            self.celery_config = config.CELERY_CONFIG
        url = self.celery_config.rabbit.dsn
        if not url:
            raise ValueError("Rabbit DSN not set")
        log.debug("Connecting to %s", url)
        await _wait_till_rabbit_responsive(url)

        # NOTE: to show the connection name in the rabbitMQ UI see there [https://www.bountysource.com/issues/89342433-setting-custom-connection-name-via-client_properties-doesn-t-work-when-connecting-using-an-amqp-url]
        self._connection = await aio_pika.connect(
            url + f"?name={__name__}_{id(socket.gethostname())}",
            client_properties={"connection_name": "sidecar connection"},
        )
        self._connection.add_close_callback(_close_callback)

        log.debug("Creating channel")
        self._channel = await self._connection.channel(publisher_confirms=False)
        self._channel.add_close_callback(_channel_close_callback)

        log.debug("Declaring %s exchange", self.celery_config.rabbit.channels["log"])
        self._logs_exchange = await self._channel.declare_exchange(
            self.celery_config.rabbit.channels["log"], aio_pika.ExchangeType.FANOUT
        )

        log.debug(
            "Declaring %s exchange",
            self.celery_config.rabbit.channels["instrumentation"],
        )
        self._instrumentation_exchange = await self._channel.declare_exchange(
            self.celery_config.rabbit.channels["instrumentation"],
            aio_pika.ExchangeType.FANOUT,
        )

    async def close(self):
        await self._channel.close()
        await self._connection.close()

    @staticmethod
    async def _post_message(
        exchange: aio_pika.Exchange, data: Dict[str, Union[str, Any]]
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
            self._logs_exchange,
            data={
                "channel": "logger",
                "node_id": node_id,
                "user_id": user_id,
                "project_id": project_id,
                "messages": log_msg if isinstance(log_msg, list) else [log_msg],
            },
        )

    async def post_progress_message(
        self, user_id: str, project_id: str, node_id: str, progress_msg: str
    ):
        await self._post_message(
            self._logs_exchange,
            data={
                "channel": "progress",
                "node_id": node_id,
                "user_id": user_id,
                "project_id": project_id,
                "progress": progress_msg,
            },
        )

    async def post_instrumentation_message(
        self,
        instrumentation_data: Dict,
    ):
        await self._post_message(
            self._instrumentation_exchange,
            data=instrumentation_data,
        )

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()


@tenacity.retry(**RabbitMQRetryPolicyUponInitialization().kwargs)
async def _wait_till_rabbit_responsive(url: RabbitDsn):
    connection = await aio_pika.connect(url)
    await connection.close()
    return True
