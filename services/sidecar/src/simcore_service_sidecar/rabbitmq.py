import json
import logging
import socket
from typing import Dict, List, Optional, Union

import aio_pika
import tenacity
from pydantic import BaseModel  # pylint: disable=no-name-in-module

from servicelib.rabbitmq_utils import RabbitMQRetryPolicyUponInitialization
from simcore_sdk.config.rabbit import Config as RabbitConfig

log = logging.getLogger(__file__)


def reconnect_callback():
    log.error("Rabbit reconnected")


def channel_close_callback(exc: Optional[BaseException]):
    if exc:
        log.error("Rabbit channel closed: %s", exc)


class RabbitMQ(BaseModel):
    config: RabbitConfig = RabbitConfig()
    connection: aio_pika.RobustConnection = None
    channel: aio_pika.Channel = None
    logs_exchange: aio_pika.Exchange = None
    progress_exchange: aio_pika.Exchange = None

    class Config:
        # see https://pydantic-docs.helpmanual.io/usage/types/#arbitrary-types-allowed
        arbitrary_types_allowed = True

    async def connect(self):
        url = self.config.broker_url
        log.debug("Connecting to %s", url)
        await wait_till_rabbit_responsive(url)

        # NOTE: to show the connection name in the rabbitMQ UI see there [https://www.bountysource.com/issues/89342433-setting-custom-connection-name-via-client_properties-doesn-t-work-when-connecting-using-an-amqp-url]
        self.connection = await aio_pika.connect_robust(
            url + f"?name={__name__}_{id(socket.gethostname())}",
            client_properties={"connection_name": "sidecar connection"},
        )
        self.connection.add_reconnect_callback(reconnect_callback)

        log.debug("Creating channel")
        self.channel = await self.connection.channel(publisher_confirms=False)
        self.channel.add_close_callback(channel_close_callback)

        log.debug("Declaring %s exchange", self.config.channels["log"])
        self.logs_exchange = await self.channel.declare_exchange(
            self.config.channels["log"], aio_pika.ExchangeType.FANOUT
        )
        log.debug("Declaring %s exchange", self.config.channels["progress"])
        self.progress_exchange = await self.channel.declare_exchange(
            self.config.channels["progress"], aio_pika.ExchangeType.FANOUT,
        )

    async def close(self):
        log.debug("Closing channel...")
        await self.channel.close()
        log.debug("Closing connection...")
        await self.connection.close()

    async def _post_message(self, exchange: aio_pika.Exchange, data: Dict[str, str]):
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


@tenacity.retry(**RabbitMQRetryPolicyUponInitialization().kwargs)
async def wait_till_rabbit_responsive(url: str):
    connection = await aio_pika.connect(url)
    await connection.close()
    return True


class RabbitMQContextManager:
    def __init__(self):
        self._rabbit_mq: RabbitMQ = None

    async def __aenter__(self):
        self._rabbit_mq = RabbitMQ()
        await self._rabbit_mq.connect()
        return self._rabbit_mq

    async def __aexit__(self, exc_type, exc, tb):
        await self._rabbit_mq.close()
