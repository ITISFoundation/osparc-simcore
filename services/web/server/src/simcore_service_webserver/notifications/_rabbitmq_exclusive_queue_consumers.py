import asyncio
import logging
from collections import defaultdict
from collections.abc import AsyncIterator, Generator
from typing import Final

from aiohttp import web
from models_library.groups import GroupID
from models_library.rabbitmq_messages import (
    EventRabbitMessage,
    LoggerRabbitMessage,
    ProgressRabbitMessageNode,
    ProgressRabbitMessageProject,
    ProgressType,
    WalletCreditsMessage,
)
from models_library.socketio import SocketMessageDict
from pydantic import TypeAdapter
from servicelib.logging_utils import log_catch, log_context
from servicelib.rabbitmq import RabbitMQClient
from servicelib.utils import logged_gather

from ..projects import _projects_service
from ..projects.exceptions import ProjectNotFoundError
from ..rabbitmq import get_rabbitmq_client
from ..socketio.messages import (
    SOCKET_IO_EVENT,
    SOCKET_IO_LOG_EVENT,
    SOCKET_IO_NODE_UPDATED_EVENT,
    SOCKET_IO_WALLET_OSPARC_CREDITS_UPDATED_EVENT,
    send_message_to_standard_group,
    send_message_to_user,
)
from ..socketio.models import WebSocketNodeProgress, WebSocketProjectProgress
from ..wallets import api as wallets_service
from ._rabbitmq_consumers_common import SubcribeArgumentsTuple, subscribe_to_rabbitmq

_logger = logging.getLogger(__name__)

_APP_RABBITMQ_CONSUMERS_KEY: Final[str] = f"{__name__}.rabbit_consumers"
APP_WALLET_SUBSCRIPTIONS_KEY: Final[str] = "wallet_subscriptions"
APP_WALLET_SUBSCRIPTION_LOCK_KEY: Final[str] = "wallet_subscription_lock"


async def _convert_to_node_update_event(
    app: web.Application, message: ProgressRabbitMessageNode
) -> SocketMessageDict | None:
    try:
        project = await _projects_service.get_project_for_user(
            app, f"{message.project_id}", message.user_id
        )
        if f"{message.node_id}" in project["workbench"]:
            # update the project node progress with the latest value
            project["workbench"][f"{message.node_id}"].update(
                {"progress": round(message.report.percent_value * 100.0)}
            )
            return SocketMessageDict(
                event_type=SOCKET_IO_NODE_UPDATED_EVENT,
                data={
                    "project_id": message.project_id,
                    "node_id": message.node_id,
                    "data": project["workbench"][f"{message.node_id}"],
                },
            )
        _logger.warning("node not found: '%s'", message.model_dump())
    except ProjectNotFoundError:
        _logger.warning("project not found: '%s'", message.model_dump())
    return None


async def _progress_message_parser(app: web.Application, data: bytes) -> bool:
    rabbit_message: ProgressRabbitMessageNode | ProgressRabbitMessageProject = (
        TypeAdapter(
            ProgressRabbitMessageNode | ProgressRabbitMessageProject
        ).validate_json(data)
    )
    message: SocketMessageDict | None = None
    if isinstance(rabbit_message, ProgressRabbitMessageProject):
        message = WebSocketProjectProgress.from_rabbit_message(
            rabbit_message
        ).to_socket_dict()

    elif rabbit_message.progress_type is ProgressType.COMPUTATION_RUNNING:
        message = await _convert_to_node_update_event(app, rabbit_message)

    else:
        message = WebSocketNodeProgress.from_rabbit_message(
            rabbit_message
        ).to_socket_dict()

    if message:
        await send_message_to_user(
            app,
            rabbit_message.user_id,
            message=message,
            ignore_queue=True,
        )
    return True


async def _log_message_parser(app: web.Application, data: bytes) -> bool:
    rabbit_message = LoggerRabbitMessage.model_validate_json(data)
    await send_message_to_user(
        app,
        rabbit_message.user_id,
        message=SocketMessageDict(
            event_type=SOCKET_IO_LOG_EVENT,
            data=rabbit_message.model_dump(exclude={"user_id", "channel_name"}),
        ),
        ignore_queue=True,
    )
    return True


async def _events_message_parser(app: web.Application, data: bytes) -> bool:
    rabbit_message = EventRabbitMessage.model_validate_json(data)
    await send_message_to_user(
        app,
        rabbit_message.user_id,
        message=SocketMessageDict(
            event_type=SOCKET_IO_EVENT,
            data={
                "action": rabbit_message.action,
                "node_id": f"{rabbit_message.node_id}",
            },
        ),
        ignore_queue=True,
    )
    return True


async def _osparc_credits_message_parser(app: web.Application, data: bytes) -> bool:
    rabbit_message = TypeAdapter(WalletCreditsMessage).validate_json(data)
    wallet_groups = await wallets_service.list_wallet_groups_with_read_access_by_wallet(
        app, wallet_id=rabbit_message.wallet_id
    )
    rooms_to_notify: Generator[GroupID, None, None] = (
        item.gid for item in wallet_groups
    )
    for room in rooms_to_notify:
        await send_message_to_standard_group(
            app,
            room,
            message=SocketMessageDict(
                event_type=SOCKET_IO_WALLET_OSPARC_CREDITS_UPDATED_EVENT,
                data={
                    "wallet_id": rabbit_message.wallet_id,
                    "osparc_credits": rabbit_message.credits,
                    "created_at": rabbit_message.created_at,
                },
            ),
        )
    return True


_EXCHANGE_TO_PARSER_CONFIG: Final[tuple[SubcribeArgumentsTuple, ...]] = (
    SubcribeArgumentsTuple(
        LoggerRabbitMessage.get_channel_name(),
        _log_message_parser,
        {"topics": []},
    ),
    SubcribeArgumentsTuple(
        ProgressRabbitMessageNode.get_channel_name(),
        _progress_message_parser,
        {"topics": []},
    ),
    SubcribeArgumentsTuple(
        EventRabbitMessage.get_channel_name(),
        _events_message_parser,
        {},
    ),
    SubcribeArgumentsTuple(
        WalletCreditsMessage.get_channel_name(),
        _osparc_credits_message_parser,
        {"topics": []},
    ),
)


async def _unsubscribe_from_rabbitmq(app) -> None:
    with log_context(
        _logger, logging.INFO, msg="Unsubscribing from rabbitmq channels"
    ), log_catch(_logger, reraise=False):
        rabbit_client: RabbitMQClient = get_rabbitmq_client(app)
        await logged_gather(
            *(
                rabbit_client.unsubscribe(queue_name)
                for queue_name, _ in app[_APP_RABBITMQ_CONSUMERS_KEY].values()
            ),
        )


async def on_cleanup_ctx_rabbitmq_consumers(
    app: web.Application,
) -> AsyncIterator[None]:
    app[_APP_RABBITMQ_CONSUMERS_KEY] = await subscribe_to_rabbitmq(
        app, _EXCHANGE_TO_PARSER_CONFIG
    )

    app[APP_WALLET_SUBSCRIPTIONS_KEY] = defaultdict(
        int
    )  # wallet_id -> subscriber count
    app[APP_WALLET_SUBSCRIPTION_LOCK_KEY] = asyncio.Lock()  # For thread-safe operations

    yield

    # cleanup
    await _unsubscribe_from_rabbitmq(app)
