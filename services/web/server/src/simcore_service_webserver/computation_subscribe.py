import asyncio
import json
import logging
from functools import wraps
from pprint import pformat
from typing import Callable, Coroutine, Dict

import aio_pika
from aiohttp import web
from servicelib.application_keys import APP_CONFIG_KEY
from servicelib.monitor_services import (
    SERVICE_STARTED_LABELS,
    SERVICE_STOPPED_LABELS,
    service_started,
    service_stopped,
)
from servicelib.rabbitmq_utils import RabbitMQRetryPolicyUponInitialization
from tenacity import retry

from .computation_config import (
    APP_CLIENT_RABBIT_DECORATED_HANDLERS_KEY,
    CONFIG_SECTION_NAME,
    ComputationSettings,
)
from .projects import projects_api
from .projects.projects_exceptions import NodeNotFoundError, ProjectNotFoundError
from .socketio.events import post_messages

log = logging.getLogger(__file__)


def rabbit_adapter(app: web.Application) -> Callable:
    """this decorator allows passing additional paramters to python-socketio compatible handlers.
    I.e. aiopika handler expect functions of type `async def function(message)`
    This allows to create a function of type `async def function(message, app: web.Application)
    """

    def decorator(func) -> Coroutine:
        @wraps(func)
        async def wrapped(*args, **kwargs) -> Coroutine:
            return await func(*args, **kwargs, app=app)

        return wrapped

    return decorator


async def parse_rabbit_message_data(app: web.Application, data: Dict) -> None:
    log.debug("parsing message data:\n%s", pformat(data, depth=3))
    # get common data
    user_id = data["user_id"]
    project_id = data["project_id"]
    node_id = data["Node"]

    try:
        messages = {}
        if data["Channel"] == "Progress":
            # update corresponding project, node, progress value
            project = await projects_api.update_project_node_progress(
                app, user_id, project_id, node_id, progress=data["Progress"]
            )
            messages["nodeUpdated"] = {
                "Node": node_id,
                "Data": project["workbench"][node_id],
            }
        elif data["Channel"] == "Log":
            messages["logger"] = data
        if messages:
            await post_messages(app, user_id, messages)
    except ProjectNotFoundError:
        log.exception("parsed rabbit message invalid")
    except NodeNotFoundError:
        log.exception("parsed rabbit message invalid")


async def rabbit_message_handler(
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


async def subscribe(app: web.Application) -> None:
    # TODO: catch and deal with missing connections:
    # e.g. CRITICAL:pika.adapters.base_connection:Could not get addresses to use: [Errno -2] Name or service not known (rabbit)
    # This exception is catch and pika persists ... WARNING:pika.connection:Could not connect, 5 attempts l

    comp_settings: ComputationSettings = app[APP_CONFIG_KEY][CONFIG_SECTION_NAME]
    rabbit_broker = comp_settings.broker_url

    log.info("Creating pika connection for %s", rabbit_broker)
    await wait_till_rabbitmq_responsive(rabbit_broker)
    # NOTE: to show the connection name in the rabbitMQ UI see there [https://www.bountysource.com/issues/89342433-setting-custom-connection-name-via-client_properties-doesn-t-work-when-connecting-using-an-amqp-url]
    connection = await aio_pika.connect_robust(
        rabbit_broker + f"?name={__name__}_{id(app)}",
        client_properties={"connection_name": "webserver read connection"},
    )

    channel = await connection.channel()
    await channel.set_qos(prefetch_count=1)

    pika_log_channel = comp_settings.rabbit.channels["log"]
    logs_exchange = await channel.declare_exchange(
        pika_log_channel, aio_pika.ExchangeType.FANOUT
    )

    # Declaring queue
    logs_progress_queue = await channel.declare_queue(
        f"webserver_{id(app)}_logs_progress",
        exclusive=True,
        arguments={"x-message-ttl": 60000},
    )

    # Binding the queue to the exchange
    await logs_progress_queue.bind(logs_exchange)

    # Start listening the queue with name 'task_queue'
    partial_rabbit_message_handler = rabbit_adapter(app)(rabbit_message_handler)
    # TODO: Why are we saving this in the app??
    app[APP_CLIENT_RABBIT_DECORATED_HANDLERS_KEY] = [partial_rabbit_message_handler]
    await logs_progress_queue.consume(
        partial_rabbit_message_handler, exclusive=True, no_ack=True
    )

    # instrumentation
    pika_instrumentation_channel = comp_settings.rabbit.channels["instrumentation"]
    instrumentation_exchange = await channel.declare_exchange(
        pika_instrumentation_channel, aio_pika.ExchangeType.FANOUT
    )
    instrumentation_queue = await channel.declare_queue(
        f"webserver_{id(app)}_instrumentation", exclusive=True
    )
    await instrumentation_queue.bind(instrumentation_exchange)
    partial_rabbit__instrumentation_handler = rabbit_adapter(app)(
        instrumentation_message_handler
    )
    app[APP_CLIENT_RABBIT_DECORATED_HANDLERS_KEY].extend(
        [partial_rabbit__instrumentation_handler]
    )
    await instrumentation_queue.consume(
        partial_rabbit__instrumentation_handler, exclusive=True, no_ack=False
    )


@retry(**RabbitMQRetryPolicyUponInitialization().kwargs)
async def wait_till_rabbitmq_responsive(url: str) -> bool:
    """Check if something responds to ``url`` """
    connection = await aio_pika.connect(url)
    await connection.close()
    return True
