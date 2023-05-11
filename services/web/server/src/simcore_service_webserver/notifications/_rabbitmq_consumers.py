import functools
import logging
from typing import Any, AsyncIterator, Callable, Coroutine, Final, Union

from aiohttp import web
from models_library.rabbitmq_messages import (
    EventRabbitMessage,
    InstrumentationRabbitMessage,
    LoggerRabbitMessage,
    ProgressRabbitMessageNode,
    ProgressRabbitMessageProject,
    ProgressType,
)
from pydantic import parse_raw_as
from servicelib.aiohttp.monitor_services import (
    SERVICE_STARTED_LABELS,
    SERVICE_STOPPED_LABELS,
    service_started,
    service_stopped,
)
from servicelib.json_serialization import json_dumps
from servicelib.logging_utils import log_context
from servicelib.rabbitmq import RabbitMQClient
from servicelib.utils import logged_gather

from ..projects import projects_api
from ..projects.projects_exceptions import NodeNotFoundError, ProjectNotFoundError
from ..rabbitmq import get_rabbitmq_client
from ..socketio.messages import (
    SOCKET_IO_EVENT,
    SOCKET_IO_LOG_EVENT,
    SOCKET_IO_NODE_PROGRESS_EVENT,
    SOCKET_IO_NODE_UPDATED_EVENT,
    SOCKET_IO_PROJECT_PROGRESS_EVENT,
    SocketMessageDict,
    send_messages,
)
from ._constants import APP_RABBITMQ_CONSUMERS_KEY

_logger = logging.getLogger(__name__)


async def _handle_computation_running_progress(
    app: web.Application, message: ProgressRabbitMessageNode
) -> bool:
    try:
        project = await projects_api.update_project_node_progress(
            app,
            message.user_id,
            f"{message.project_id}",
            f"{message.node_id}",
            progress=message.progress,
        )
        if project and not await projects_api.is_project_hidden(
            app, message.project_id
        ):
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
        _logger.warning(
            "project related to received rabbitMQ progress message not found: '%s'",
            json_dumps(message, indent=2),
        )
        return True
    except NodeNotFoundError:
        _logger.warning(
            "node related to received rabbitMQ progress message not found: '%s'",
            json_dumps(message, indent=2),
        )
        return True
    return False


async def _progress_message_parser(app: web.Application, data: bytes) -> bool:
    # update corresponding project, node, progress value
    rabbit_message: (
        ProgressRabbitMessageNode | ProgressRabbitMessageProject
    ) = parse_raw_as(
        Union[ProgressRabbitMessageNode, ProgressRabbitMessageProject], data
    )

    if rabbit_message.progress_type is ProgressType.COMPUTATION_RUNNING:
        # NOTE: backward compatibility, this progress is kept in the project
        assert isinstance(rabbit_message, ProgressRabbitMessageNode)  # nosec
        return await _handle_computation_running_progress(app, rabbit_message)

    # NOTE: other types of progress are transient
    is_type_message_node = type(rabbit_message) == ProgressRabbitMessageNode
    socket_message: SocketMessageDict = {
        "event_type": (
            SOCKET_IO_NODE_PROGRESS_EVENT
            if is_type_message_node
            else SOCKET_IO_PROJECT_PROGRESS_EVENT
        ),
        "data": {
            "project_id": rabbit_message.project_id,
            "user_id": rabbit_message.user_id,
            "progress_type": rabbit_message.progress_type,
            "progress": rabbit_message.progress,
        },
    }
    if is_type_message_node:
        socket_message["data"]["node_id"] = rabbit_message.node_id
    await send_messages(app, f"{rabbit_message.user_id}", [socket_message])
    return True


async def _log_message_parser(app: web.Application, data: bytes) -> bool:
    rabbit_message = LoggerRabbitMessage.parse_raw(data)

    if not await projects_api.is_project_hidden(app, rabbit_message.project_id):
        socket_messages: list[SocketMessageDict] = [
            {
                "event_type": SOCKET_IO_LOG_EVENT,
                "data": rabbit_message.dict(exclude={"user_id", "channel_name"}),
            }
        ]
        await send_messages(app, f"{rabbit_message.user_id}", socket_messages)
    return True


async def _instrumentation_message_parser(app: web.Application, data: bytes) -> bool:
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


async def _events_message_parser(app: web.Application, data: bytes) -> bool:
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


EXCHANGE_TO_PARSER_CONFIG: Final[
    tuple[
        tuple[
            str,
            Callable[[web.Application, bytes], Coroutine[Any, Any, bool]],
            dict[str, Any],
        ],
        ...,
    ]
] = (
    (
        LoggerRabbitMessage.get_channel_name(),
        _log_message_parser,
        dict(topics=[]),
    ),
    (
        ProgressRabbitMessageNode.get_channel_name(),
        _progress_message_parser,
        {},
    ),
    (
        InstrumentationRabbitMessage.get_channel_name(),
        _instrumentation_message_parser,
        dict(exclusive_queue=False),
    ),
    (
        EventRabbitMessage.get_channel_name(),
        _events_message_parser,
        {},
    ),
)


async def setup_rabbitmq_consumers(app: web.Application) -> AsyncIterator[None]:
    with log_context(_logger, logging.INFO, msg="Subscribing to rabbitmq channels"):
        rabbit_client: RabbitMQClient = get_rabbitmq_client(app)
        subscribed_queues = await logged_gather(
            *(
                rabbit_client.subscribe(
                    exchange_name, functools.partial(parser_fct, app), **queue_kwargs
                )
                for exchange_name, parser_fct, queue_kwargs in EXCHANGE_TO_PARSER_CONFIG
            )
        )
        app[APP_RABBITMQ_CONSUMERS_KEY] = {
            exchange_name: queue_name
            for (exchange_name, *_), queue_name in zip(
                EXCHANGE_TO_PARSER_CONFIG, subscribed_queues
            )
        }

    yield

    # cleanup
    with log_context(_logger, logging.INFO, msg="Unsubscribing from rabbitmq channels"):
        rabbit_client: RabbitMQClient = get_rabbitmq_client(app)
        await logged_gather(
            *(
                rabbit_client.unsubscribe(queue_name)
                for queue_name in subscribed_queues
            ),
            reraise=False,
        )
