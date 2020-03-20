import json
import logging
from typing import Dict, List, Union

import aio_pika
import tenacity
from pydantic import BaseModel

from servicelib.rabbitmq_utils import RabbitMQRetryPolicyUponInitialization
from simcore_sdk.config.rabbit import Config as RabbitConfig

log = logging.getLogger(__file__)


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
        await wait_till_rabbit_responsive(url)

        self.connection = await aio_pika.connect_robust(
            url, client_properties={"connection_name": "sidecar connection"},
        )

        self.channel = await self.connection.channel()
        self.logs_exchange = await self.channel.declare_exchange(
            self.config.channels["log"], aio_pika.ExchangeType.FANOUT, auto_delete=True
        )
        self.progress_exchange = await self.channel.declare_exchange(
            self.config.channels["progress"],
            aio_pika.ExchangeType.FANOUT,
            auto_delete=True,
        )

    async def close(self):
        await self.channel.close()
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
                "Messages": progress_msg,
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
