import asyncio
import contextlib
import json
import logging
import socket
from typing import Any, AsyncIterator, Awaitable, Callable, Dict, List

import aio_pika
from aiohttp import web
from servicelib.aiohttp.monitor_services import (
    SERVICE_STARTED_LABELS,
    SERVICE_STOPPED_LABELS,
    service_started,
    service_stopped,
)
from servicelib.rabbitmq_utils import RabbitMQRetryPolicyUponInitialization
from tenacity import retry

from .computation_config import ComputationSettings
from .computation_config import get_settings as get_computation_settings
from .projects import projects_api
from .projects.projects_exceptions import NodeNotFoundError, ProjectNotFoundError
from .socketio.events import (
    SOCKET_IO_LOG_EVENT,
    SOCKET_IO_NODE_UPDATED_EVENT,
    SocketMessageDict,
    send_messages,
)

log = logging.getLogger(__file__)


async def progress_message_parser(app: web.Application, data: Dict[str, Any]) -> None:
    # update corresponding project, node, progress value
    user_id = data["user_id"]
    project_id = data["project_id"]
    node_id = data["node_id"]
    try:
        project = await projects_api.update_project_node_progress(
            app, user_id, project_id, node_id, progress=data["progress"]
        )
        if project:
            messages: List[SocketMessageDict] = [
                {
                    "event_type": SOCKET_IO_NODE_UPDATED_EVENT,
                    "data": {
                        "node_id": node_id,
                        "data": project["workbench"][node_id],
                    },
                }
            ]
            await send_messages(app, user_id, messages)
    except ProjectNotFoundError:
        log.warning(
            "project related to received rabbitMQ progress message not found: '%s'",
            json.dumps(data, indent=2),
        )
    except NodeNotFoundError:
        log.warning(
            "node related to received rabbitMQ progress message not found: '%s'",
            json.dumps(data, indent=2),
        )


async def log_message_parser(app: web.Application, data: Dict[str, Any]) -> None:
    messages: List[SocketMessageDict] = [
        {"event_type": SOCKET_IO_LOG_EVENT, "data": data}
    ]
    await send_messages(app, data["user_id"], messages)


async def instrumentation_message_parser(
    app: web.Application, data: Dict[str, Any]
) -> None:
    if data["metrics"] == "service_started":
        service_started(app, **{key: data[key] for key in SERVICE_STARTED_LABELS})
    elif data["metrics"] == "service_stopped":
        service_stopped(app, **{key: data[key] for key in SERVICE_STOPPED_LABELS})


async def rabbitmq_consumer(app: web.Application) -> AsyncIterator[None]:
    # TODO: catch and deal with missing connections:
    # e.g. CRITICAL:pika.adapters.base_connection:Could not get addresses to use: [Errno -2] Name or service not known (rabbit)
    # This exception is catch and pika persists ... WARNING:pika.connection:Could not connect, 5 attempts l
    comp_settings: ComputationSettings = get_computation_settings(app)
    rabbit_broker = comp_settings.broker_url

    log.info("Creating pika connection pool for %s", rabbit_broker)
    await wait_till_rabbitmq_responsive(f"{rabbit_broker}")
    # NOTE: to show the connection name in the rabbitMQ UI see there [https://www.bountysource.com/issues/89342433-setting-custom-connection-name-via-client_properties-doesn-t-work-when-connecting-using-an-amqp-url]
    async def get_connection() -> aio_pika.Connection:
        return await aio_pika.connect_robust(
            f"{rabbit_broker}" + f"?name={__name__}_{socket.gethostname()}_{id(app)}",
            client_properties={"connection_name": "webserver read connection"},
        )

    connection_pool = aio_pika.pool.Pool(get_connection, max_size=2)

    async def get_channel() -> aio_pika.Channel:
        async with connection_pool.acquire() as connection:
            channel = await connection.channel()
            # Finding a suitable prefetch value is a matter of trial and error
            # and will vary from workload to workload. Values in the 100
            # through 300 range usually offer optimal throughput and do not
            # run significant risk of overwhelming consumers. Higher values
            # often run into the law of diminishing returns.
            # Prefetch value of 1 is the most conservative. It will significantly
            # reduce throughput, in particular in environments where consumer
            # connection latency is high. For many applications, a higher value
            # would be appropriate and optimal.
            await channel.set_qos(prefetch_count=100)
            return channel

    channel_pool = aio_pika.pool.Pool(get_channel, max_size=10)

    async def exchange_consumer(
        exchange_name: str,
        parse_handler: Callable[[web.Application, Dict[str, Any]], Awaitable[None]],
        consumer_kwargs: Dict[str, Any],
    ):
        while True:
            try:
                async with channel_pool.acquire() as channel:
                    exchange = await channel.declare_exchange(
                        exchange_name, aio_pika.ExchangeType.FANOUT
                    )
                    # Declaring queue
                    queue = await channel.declare_queue(
                        f"webserver_{socket.gethostname()}_{id(app)}_{exchange_name}",
                        exclusive=True,
                        arguments={"x-message-ttl": 60000},
                    )
                    # Binding the queue to the exchange
                    await queue.bind(exchange)
                    # process
                    async with queue.iterator(
                        exclusive=True, **consumer_kwargs
                    ) as queue_iter:
                        async for message in queue_iter:
                            log.debug(
                                "Received message from exchange %s", exchange_name
                            )
                            data = json.loads(message.body)
                            await parse_handler(app, data)
                            log.debug("message parsed")
            except asyncio.CancelledError:
                log.info("stopping rabbitMQ consumer for %s", exchange_name)
                raise
            except Exception:  # pylint: disable=broad-except
                log.warning(
                    "unexpected error in consumer for %s, restarting",
                    exchange_name,
                    exc_info=True,
                )

    consumer_tasks = []
    for exchange_name, message_parser, consumer_kwargs in [
        (
            comp_settings.rabbit.channels["log"],
            log_message_parser,
            {"no_ack": True},
        ),
        (
            comp_settings.rabbit.channels["progress"],
            progress_message_parser,
            {"no_ack": True},
        ),
        (
            comp_settings.rabbit.channels["instrumentation"],
            instrumentation_message_parser,
            {"no_ack": False},
        ),
    ]:
        task = asyncio.create_task(
            exchange_consumer(exchange_name, message_parser, consumer_kwargs)
        )
        consumer_tasks.append(task)

    log.info("Connected to rabbitMQ exchanges")

    yield

    # cleanup
    log.info("Disconnecting from rabbitMQ exchanges...")
    for task in consumer_tasks:
        task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        for task in consumer_tasks:
            await task
    log.info("Closing connections...")
    await channel_pool.close()
    await connection_pool.close()
    log.info("closed.")


@retry(**RabbitMQRetryPolicyUponInitialization().kwargs)
async def wait_till_rabbitmq_responsive(url: str) -> bool:
    """Check if something responds to ``url``"""
    connection = await aio_pika.connect(url)
    await connection.close()
    return True
