import asyncio
import json
import logging
from functools import wraps
from pprint import pprint
from typing import Callable, Coroutine, Dict

import aio_pika
from aiohttp import web

from servicelib.application_keys import APP_CONFIG_KEY
from simcore_sdk.config.rabbit import eval_broker

from .computation_api import get_task_output
from .computation_config import (APP_CLIENT_RABBIT_DECORATED_HANDLERS_KEY,
                                 CONFIG_SECTION_NAME)
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
    log.debug("parsing message data:\n%s", pprint(data))
    # get common data
    user_id = data["user_id"]
    project_id = data["project_id"]
    node_id = data["Node"]

    try:
        messages = {}
        if data["Channel"] == "Progress":
            # update corresponding project, node, progress value
            node_data = await projects_api.update_project_node_progress(app, user_id, project_id, node_id, progress=data["Progress"])
            messages["nodeUpdated"] = {"Node": node_id, "Data": node_data}
        elif data["Channel"] == "Log":
            messages["logger"] = data
            if "...postprocessing end" in data["Messages"]:
                # the computational service completed
                # pass comp_task payload to project
                task_output = await get_task_output(app, project_id, node_id)
                node_data = await projects_api.update_project_node_outputs(app, user_id, project_id, node_id, data=task_output)
                messages["nodeUpdated"] = {"Node": node_id, "Data": node_data}

        if messages:
            await post_messages(app, user_id, messages)
    except ProjectNotFoundError:
        log.exception("parsed rabbit message invalid")
    except NodeNotFoundError:
        log.exception("parsed rabbit message invalid")


async def rabbit_message_handler(message: aio_pika.IncomingMessage, app: web.Application) -> None:
    with message.process():
        data = json.loads(message.body)
        await parse_rabbit_message_data(app, data)

async def subscribe(app: web.Application) -> None:
    # TODO: catch and deal with missing connections:
    # e.g. CRITICAL:pika.adapters.base_connection:Could not get addresses to use: [Errno -2] Name or service not known (rabbit)
    # This exception is catch and pika persists ... WARNING:pika.connection:Could not connect, 5 attempts l

    rb_config: Dict = app[APP_CONFIG_KEY][CONFIG_SECTION_NAME]
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
    partial_rabbit_message_handler = rabbit_adapter(app)(rabbit_message_handler)
    app[APP_CLIENT_RABBIT_DECORATED_HANDLERS_KEY] = [partial_rabbit_message_handler]
    await queue.consume(partial_rabbit_message_handler)
