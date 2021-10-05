import asyncio
import functools
import json
import logging
from pprint import pformat
from typing import AsyncIterator, Awaitable, Callable, Dict

import aio_pika
from aiohttp import web
from aiohttp.web_app import Application
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
from .socketio.events import post_messages

log = logging.getLogger(__file__)


async def parse_rabbit_message_data(app: web.Application, data: Dict) -> None:
    log.debug("parsing message data:\n%s", pformat(data, depth=3))
    # get common data
    user_id = data["user_id"]
    project_id = data["project_id"]
    node_id = data["node_id"]

    try:
        messages = {}
        if data["channel"] == "progress":
            # update corresponding project, node, progress value
            project = await projects_api.update_project_node_progress(
                app, user_id, project_id, node_id, progress=data["progress"]
            )
            if project:
                messages["nodeUpdated"] = {
                    "node_id": node_id,
                    "data": project["workbench"][node_id],
                }
        elif data["channel"] == "log":
            messages["logger"] = data
        if messages:
            await post_messages(app, user_id, messages)
    except ProjectNotFoundError:
        log.exception("parsed rabbit message invalid")
    except NodeNotFoundError:
        log.exception("parsed rabbit message invalid")


async def rabbit_logs_handler(
    message: aio_pika.IncomingMessage, app: web.Application
) -> None:
    data = json.loads(message.body)
    # TODO: create a task here instead of blocking
    await parse_rabbit_message_data(app, data)
    # NOTE: this allows the webserver to breath if a lot of messages are entering
    await asyncio.sleep(1)


async def instrumentation_message_handler(
    message: aio_pika.IncomingMessage, app: web.Application
) -> None:
    data = json.loads(message.body)
    if data["metrics"] == "service_started":
        service_started(app, **{key: data[key] for key in SERVICE_STARTED_LABELS})
    elif data["metrics"] == "service_stopped":
        service_stopped(app, **{key: data[key] for key in SERVICE_STOPPED_LABELS})
    await message.ack()


async def rabbitmq_consumer(app: web.Application) -> AsyncIterator[None]:
    # TODO: catch and deal with missing connections:
    # e.g. CRITICAL:pika.adapters.base_connection:Could not get addresses to use: [Errno -2] Name or service not known (rabbit)
    # This exception is catch and pika persists ... WARNING:pika.connection:Could not connect, 5 attempts l

    comp_settings: ComputationSettings = get_computation_settings(app)
    rabbit_broker = comp_settings.broker_url

    log.info("Creating pika connection for %s", rabbit_broker)
    await wait_till_rabbitmq_responsive(f"{rabbit_broker}")
    # NOTE: to show the connection name in the rabbitMQ UI see there [https://www.bountysource.com/issues/89342433-setting-custom-connection-name-via-client_properties-doesn-t-work-when-connecting-using-an-amqp-url]
    connection = await aio_pika.connect_robust(
        f"{rabbit_broker}" + f"?name={__name__}_{id(app)}",
        client_properties={"connection_name": "webserver read connection"},
    )

    channel = await connection.channel()
    await channel.set_qos(prefetch_count=1)

    async def _connect_to_queue(
        name: str,
        handler: Callable[[aio_pika.IncomingMessage, Application], Awaitable[None]],
        no_ack: bool,
    ):
        exchange = await channel.declare_exchange(name, aio_pika.ExchangeType.FANOUT)
        # Declaring queue
        queue = await channel.declare_queue(
            f"webserver_{id(app)}_{name}",
            exclusive=True,
            arguments={"x-message-ttl": 60000},
        )
        # Binding the queue to the exchange
        await queue.bind(exchange)
        # pass the handler
        await queue.consume(
            functools.partial(handler, app=app),
            exclusive=True,
            no_ack=no_ack,
        )

    await _connect_to_queue(
        comp_settings.rabbit.channels["log"], rabbit_logs_handler, no_ack=True
    )
    await _connect_to_queue(
        comp_settings.rabbit.channels["progress"], rabbit_logs_handler, no_ack=True
    )
    await _connect_to_queue(
        comp_settings.rabbit.channels["instrumentation"],
        instrumentation_message_handler,
        no_ack=False,
    )
    log.info("Connected to rabbitMQ exchanges")

    yield

    # cleanup
    await connection.close()


@retry(**RabbitMQRetryPolicyUponInitialization().kwargs)
async def wait_till_rabbitmq_responsive(url: str) -> bool:
    """Check if something responds to ``url``"""
    connection = await aio_pika.connect(url)
    await connection.close()
    return True
