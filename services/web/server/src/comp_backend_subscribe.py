import json
import logging

import aio_pika

from async_sio import SIO
from simcore_sdk.config.rabbit import Config as rabbit_config

_LOGGER = logging.getLogger(__file__)

# rabbit config
rabbit_config = rabbit_config()
pika_log_channel = rabbit_config.log_channel
pika_progress_channel = rabbit_config.progress_channel
rabbit_broker = rabbit_config.broker

async def on_message(message: aio_pika.IncomingMessage):
    with message.process():
        data = json.loads(message.body)
        _LOGGER.debug(data)
        if data["Channel"] == "Log":
            await SIO.emit("logger", data = json.dumps(data))
        elif data["Channel"] == "Progress":
            await SIO.emit("progress", data = json.dumps(data))

async def subscribe(_app=None):
    connection = await aio_pika.connect(rabbit_broker, connection_attempts=100)
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=1)

    logs_exchange = await channel.declare_exchange(
        pika_log_channel, aio_pika.ExchangeType.FANOUT
    )

    progress_exchange = await channel.declare_exchange(
        pika_progress_channel, aio_pika.ExchangeType.FANOUT
    )

    # Declaring queue
    queue = await channel.declare_queue(exclusive=True)

    # Binding the queue to the exchange
    await queue.bind(logs_exchange)
    await queue.bind(progress_exchange)

    # Start listening the queue with name 'task_queue'
    await queue.consume(on_message)
