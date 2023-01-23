import functools
import logging
from typing import AsyncIterator

from aiohttp import web
from models_library.rabbitmq_messages import (
    EventRabbitMessage,
    InstrumentationRabbitMessage,
    LoggerRabbitMessage,
    ProgressRabbitMessage,
    ProgressType,
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
    SOCKET_IO_NODE_PROGRESS_EVENT,
    SOCKET_IO_NODE_UPDATED_EVENT,
    SocketMessageDict,
    send_messages,
)

log = logging.getLogger(__name__)


async def _handle_computation_running_progress(
    app: web.Application, message: ProgressRabbitMessage
) -> bool:
    try:
        project = await projects_api.update_project_node_progress(
            app,
            message.user_id,
            f"{message.project_id}",
            f"{message.node_id}",
            progress=message.progress,
        )
        if project:
            messages: list[SocketMessageDict] = [
                {
                    "event_type": SOCKET_IO_NODE_UPDATED_EVENT,
                    "data": {
                        "project_id": message.project_id,
                        "node_id": message.node_id,
                        "data": project["workbench"][f"{message.node_id}"],
                    },
                }
            ]
            await send_messages(app, f"{message.user_id}", messages)
            return True
    except ProjectNotFoundError:
        log.warning(
            "project related to received rabbitMQ progress message not found: '%s'",
            json_dumps(message, indent=2),
        )
        return True
    except NodeNotFoundError:
        log.warning(
            "node related to received rabbitMQ progress message not found: '%s'",
            json_dumps(message, indent=2),
        )
        return True
    return False


async def progress_message_parser(app: web.Application, data: bytes) -> bool:
    # update corresponding project, node, progress value
    rabbit_message = ProgressRabbitMessage.parse_raw(data)

    if rabbit_message.progress_type is ProgressType.COMPUTATION_RUNNING:
        # NOTE: backward compatibility, this progress is kept in the project
        return await _handle_computation_running_progress(app, rabbit_message)

    # NOTE: other types of progress are transient
    await send_messages(
        app,
        f"{rabbit_message.user_id}",
        [
            {
                "event_type": SOCKET_IO_NODE_PROGRESS_EVENT,
                "data": {
                    "project_id": rabbit_message.project_id,
                    "node_id": rabbit_message.node_id,
                    "user_id": rabbit_message.user_id,
                    "progress_type": rabbit_message.progress_type,
                    "progress": rabbit_message.progress,
                },
            }
        ],
    )
    return True


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


EXCHANGE_TO_PARSER_CONFIG = (
    (
        LoggerRabbitMessage.get_channel_name(),
        log_message_parser,
        {},
    ),
    (
        ProgressRabbitMessage.get_channel_name(),
        progress_message_parser,
        {},
    ),
    (
        InstrumentationRabbitMessage.get_channel_name(),
        instrumentation_message_parser,
        dict(exclusive_queue=False),
    ),
    (
        EventRabbitMessage.get_channel_name(),
        events_message_parser,
        {},
    ),
)


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

        for exchange_name, parser_fct, queue_kwargs in EXCHANGE_TO_PARSER_CONFIG:
            await rabbit_client.subscribe(
                exchange_name, functools.partial(parser_fct, app), **queue_kwargs
            )

    yield

    # cleanup
    with log_context(log, logging.INFO, msg="Closing RabbitMQ client"):
        await rabbit_client.close()
