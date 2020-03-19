import json
import logging
from typing import Dict, List, Union

import aio_pika
import tenacity
from pydantic import BaseModel

from servicelib.rabbitmq_utils import RabbitMQRetryPolicyUponInitialization
from simcore_sdk.config.rabbit import Config as RabbitConfig
from simcore_sdk.config.rabbit import eval_broker

log = logging.getLogger(__file__)


class RabbitMQ(BaseModel):
    _config: RabbitConfig = RabbitConfig()
    _connection: aio_pika.RobustConnection = None
    _channel: aio_pika.Channel = None
    _logs_exchange: aio_pika.Exchange = None
    _progress_exchange: aio_pika.Exchange = None

    class Config:

        arbitrary_types_allowed = True

    async def connect(self):
        url = eval_broker(self._config)
        await wait_till_rabbit_responsive(url)

        self._connection = await aio_pika.connect_robust(
            url, client_properties={"connection_name": "sidecar connection"},
        )

        self._channel = await self._connection.channel()
        self._logs_exchange = await self._channel.declare_exchange(
            self._config.log_channel, aio_pika.ExchangeType.FANOUT, auto_delete=True
        )
        self._progress_exchange = await self._channel.declare_exchange(
            self._config.progress_channel,
            aio_pika.ExchangeType.FANOUT,
            auto_delete=True,
        )

    async def close(self):
        await self._channel.close()
        await self._connection.close()

    async def _post_message(self, exchange: aio_pika.Exchange, data: Dict[str, str]):
        await exchange.publish(message=json.dumps(data))

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
            self._logs_exchange,
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
