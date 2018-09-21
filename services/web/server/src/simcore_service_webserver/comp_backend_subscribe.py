import json
import logging
import asyncio
import aio_pika

from simcore_sdk.config.rabbit import eval_broker

from .sockets import SIO

log = logging.getLogger(__file__)
SERVICE_NAME = 'rabbit'

async def on_message(message: aio_pika.IncomingMessage):
    with message.process():
        data = json.loads(message.body)
        log.debug(data)
        if data["Channel"] == "Log":
            await SIO.emit("logger", data = json.dumps(data))
        elif data["Channel"] == "Progress":
            await SIO.emit("progress", data = json.dumps(data))

async def subscribe(_app=None):
    # TODO: catch and deal with missing connections:
    # e.g. CRITICAL:pika.adapters.base_connection:Could not get addresses to use: [Errno -2] Name or service not known (rabbit)
    # This exception is catch and pika persists ... WARNING:pika.connection:Could not connect, 5 attempts l

    rb_config = _app["config"][SERVICE_NAME]
    rabbit_broker = eval_broker(rb_config)

    # FIXME: This tmp resolves ``aio pika 169: IncompatibleProtocolError`` upon apio_pika.connect
    await asyncio.sleep(5)

    # TODO: connection attempts should be configurable??
    # TODO: A contingency plan or connection policy should be defined per service! E.g. critical, lazy, partial (i.e. some parts of the service cannot run now)
    connection = await aio_pika.connect(rabbit_broker, connection_attempts=100)

    channel = await connection.channel()
    await channel.set_qos(prefetch_count=1)

    pika_log_channel = rb_config["channels"]["log"]
    logs_exchange = await channel.declare_exchange(
        pika_log_channel, aio_pika.ExchangeType.FANOUT,
        auto_delete=True
    )

    pika_progress_channel = rb_config["channels"]["progress"]
    progress_exchange = await channel.declare_exchange(
        pika_progress_channel, aio_pika.ExchangeType.FANOUT,
        auto_delete=True
    )

    # Declaring queue
    queue = await channel.declare_queue(exclusive=True)

    # Binding the queue to the exchange
    await queue.bind(logs_exchange)
    await queue.bind(progress_exchange)

    # Start listening the queue with name 'task_queue'
    await queue.consume(on_message)
