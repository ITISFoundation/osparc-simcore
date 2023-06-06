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
from servicelib.logging_utils import log_context
from servicelib.rabbitmq import RabbitMQClient
from servicelib.utils import logged_gather

from ..projects import projects_api
from ..projects.exceptions import ProjectNotFoundError
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


def _convert_to_project_progress_event(
    message: ProgressRabbitMessageProject,
) -> SocketMessageDict:
    return SocketMessageDict(
        event_type=SOCKET_IO_PROJECT_PROGRESS_EVENT,
        data={
            "project_id": message.project_id,
            "user_id": message.user_id,
            "progress_type": message.progress_type,
            "progress": message.progress,
        },
    )


async def _convert_to_node_update_event(
    app: web.Application, message: ProgressRabbitMessageNode
) -> SocketMessageDict | None:
    try:
        project = await projects_api.get_project_for_user(
            app, f"{message.project_id}", message.user_id
        )
        if f"{message.node_id}" in project["workbench"]:
            # update the project node progress with the latest value
            project["workbench"][f"{message.node_id}"].update(
                {"progress": round(message.progress * 100.0)}
            )
            return SocketMessageDict(
                event_type=SOCKET_IO_NODE_UPDATED_EVENT,
                data={
                    "project_id": message.project_id,
                    "node_id": message.node_id,
                    "data": project["workbench"][f"{message.node_id}"],
                },
            )
        _logger.warning("node not found: '%s'", message.dict())
    except ProjectNotFoundError:
        _logger.warning("project not found: '%s'", message.dict())
    return None


def _convert_to_node_progress_event(
    message: ProgressRabbitMessageNode,
) -> SocketMessageDict:
    return SocketMessageDict(
        event_type=SOCKET_IO_NODE_PROGRESS_EVENT,
        data={
            "project_id": message.project_id,
            "node_id": message.node_id,
            "user_id": message.user_id,
            "progress_type": message.progress_type,
            "progress": message.progress,
        },
    )


async def _progress_message_parser(app: web.Application, data: bytes) -> bool:
    rabbit_message = parse_raw_as(
        Union[ProgressRabbitMessageNode, ProgressRabbitMessageProject], data
    )
    socket_message: SocketMessageDict | None = None
    if isinstance(rabbit_message, ProgressRabbitMessageProject):
        socket_message = _convert_to_project_progress_event(rabbit_message)
    elif rabbit_message.progress_type is ProgressType.COMPUTATION_RUNNING:
        socket_message = await _convert_to_node_update_event(app, rabbit_message)
    else:
        socket_message = _convert_to_node_progress_event(rabbit_message)
    if socket_message:
        await send_messages(app, rabbit_message.user_id, [socket_message])

    return True


async def _log_message_parser(app: web.Application, data: bytes) -> bool:
    rabbit_message = LoggerRabbitMessage.parse_raw(data)
    socket_messages: list[SocketMessageDict] = [
        {
            "event_type": SOCKET_IO_LOG_EVENT,
            "data": rabbit_message.dict(exclude={"user_id", "channel_name"}),
        }
    ]
    await send_messages(app, rabbit_message.user_id, socket_messages)
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
    await send_messages(app, rabbit_message.user_id, socket_messages)
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
        dict(topics=[]),
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
