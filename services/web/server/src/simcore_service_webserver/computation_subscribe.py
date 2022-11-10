import functools
import logging
from typing import AsyncIterator

from aiohttp import web
from models_library.rabbitmq_messages import (
    EventRabbitMessage,
    InstrumentationRabbitMessage,
    LoggerRabbitMessage,
    ProgressRabbitMessage,
)
from servicelib.aiohttp.monitor_services import (
    SERVICE_STARTED_LABELS,
    SERVICE_STOPPED_LABELS,
    service_started,
    service_stopped,
)
from servicelib.json_serialization import json_dumps
from servicelib.logging_utils import log_context
from servicelib.rabbitmq import RabbitMQClient
from servicelib.rabbitmq_utils import wait_till_rabbitmq_responsive

from .computation_settings import RabbitSettings, get_plugin_settings
from .projects import projects_api
from .projects.projects_exceptions import NodeNotFoundError, ProjectNotFoundError
from .socketio.events import (
    SOCKET_IO_EVENT,
    SOCKET_IO_LOG_EVENT,
    SOCKET_IO_NODE_UPDATED_EVENT,
    SocketMessageDict,
    send_messages,
)

log = logging.getLogger(__name__)


async def progress_message_parser(app: web.Application, data: bytes) -> bool:
    # update corresponding project, node, progress value
    rabbit_message = ProgressRabbitMessage.parse_raw(data)
    try:
        project = await projects_api.update_project_node_progress(
            app,
            rabbit_message.user_id,
            f"{rabbit_message.project_id}",
            f"{rabbit_message.node_id}",
            progress=rabbit_message.progress,
        )
        if project:
            messages: list[SocketMessageDict] = [
                {
                    "event_type": SOCKET_IO_NODE_UPDATED_EVENT,
                    "data": {
                        "project_id": project["uuid"],
                        "node_id": rabbit_message.node_id,
                        "data": project["workbench"][f"{rabbit_message.node_id}"],
                    },
                }
            ]
            await send_messages(app, f"{rabbit_message.user_id}", messages)
            return True
    except ProjectNotFoundError:
        log.warning(
            "project related to received rabbitMQ progress message not found: '%s'",
            json_dumps(rabbit_message, indent=2),
        )
        return True
    except NodeNotFoundError:
        log.warning(
            "node related to received rabbitMQ progress message not found: '%s'",
            json_dumps(rabbit_message, indent=2),
        )
        return True
    return False


async def log_message_parser(app: web.Application, data: bytes) -> bool:
    rabbit_message = LoggerRabbitMessage.parse_raw(data)

    socket_messages: list[SocketMessageDict] = [
        {
            "event_type": SOCKET_IO_LOG_EVENT,
            "data": rabbit_message.dict(exclude={"user_id"}),
        }
    ]
    await send_messages(app, f"{rabbit_message.user_id}", socket_messages)
    return True


async def instrumentation_message_parser(app: web.Application, data: bytes) -> bool:
    rabbit_message = InstrumentationRabbitMessage.parse_raw(data)
    if rabbit_message.metrics == "service_started":
        service_started(
            app, **{key: rabbit_message.dict()[key] for key in SERVICE_STARTED_LABELS}
        )
    elif rabbit_message.metrics == "service_stopped":
        service_stopped(
            app, **{key: rabbit_message.dict()[key] for key in SERVICE_STOPPED_LABELS}
        )
    return True


async def events_message_parser(app: web.Application, data: bytes) -> bool:
    rabbit_message = EventRabbitMessage.parse_raw(data)

    socket_messages: list[SocketMessageDict] = [
        {
            "event_type": SOCKET_IO_EVENT,
            "data": {
                "action": rabbit_message.action,
                "node_id": f"{rabbit_message.node_id}",
            },
        }
    ]
    await send_messages(app, f"{rabbit_message.user_id}", socket_messages)
    return True


async def setup_rabbitmq_consumer(app: web.Application) -> AsyncIterator[None]:
    settings: RabbitSettings = get_plugin_settings(app)
    with log_context(
        log, logging.INFO, msg=f"Check RabbitMQ backend is ready on {settings.dsn}"
    ):
        await wait_till_rabbitmq_responsive(f"{settings.dsn}")

    with log_context(
        log, logging.INFO, msg=f"Connect RabbitMQ client to {settings.dsn}"
    ):
        rabbit_client = RabbitMQClient("webserver", settings)

        EXCHANGE_TO_PARSER_CONFIG = (
            (
                settings.RABBIT_CHANNELS["log"],
                log_message_parser,
                {"no_ack": True},
            ),
            (
                settings.RABBIT_CHANNELS["progress"],
                progress_message_parser,
                {"no_ack": True},
            ),
            (
                settings.RABBIT_CHANNELS["instrumentation"],
                instrumentation_message_parser,
                {"no_ack": False},
            ),
            (
                settings.RABBIT_CHANNELS["events"],
                events_message_parser,
                {"no_ack": False},
            ),
        )

        for exchange_name, parser_fct, _exchange_kwargs in EXCHANGE_TO_PARSER_CONFIG:
            await rabbit_client.consume(
                exchange_name, functools.partial(parser_fct, app)
            )

    yield

    # cleanup
    with log_context(log, logging.INFO, msg="Closing RabbitMQ client"):
        await rabbit_client.close()
