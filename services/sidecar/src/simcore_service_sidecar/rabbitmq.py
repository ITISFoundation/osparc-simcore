import logging

import aio_pika
import attr
import tenacity

from servicelib.rabbitmq_utils import RabbitMQRetryPolicyUponInitialization
from simcore_sdk.config.rabbit import Config, eval_broker

log = logging.getLogger(__file__)

@attr.s(auto_attribs=True)
class RabbitMQ:
    _config: Config = Config()
    _connection: aio_pika.RobustConnection = None
    _channel: aio_pika.Channel = None
    logs_exchange: aio_pika.Exchange = None    
    progress_exchange: aio_pika.Exchange = None

    async def connect(self):
        url = eval_broker(self._config)
        await wait_till_rabbit_responsive(url)


        self._connection = await aio_pika.connect_robust(
            url,
            client_properties={"connection_name": "sidecar connection"},
        )

        self._channel = await self._connection.channel()
        self.logs_exchange = await self._channel.declare_exchange(
            self._config.log_channel, aio_pika.ExchangeType.FANOUT, auto_delete=True
        )
        self.progress_exchange = await self._channel.declare_exchange(
            self._config.progress_channel, aio_pika.ExchangeType.FANOUT, auto_delete=True
        )

    async def post_message(self):
        


@tenacity.retry(**RabbitMQRetryPolicyUponInitialization().kwargs)
async def wait_till_rabbit_responsive(url: str):
    connection = await aio_pika.connect(url)
    await connection.close()
    return True