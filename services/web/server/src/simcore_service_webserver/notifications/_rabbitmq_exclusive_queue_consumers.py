import asyncio
import logging
from collections import defaultdict
from collections.abc import AsyncIterator, Generator, MutableMapping
from typing import Final

from aiohttp import web
from models_library.groups import GroupID
from models_library.projects import ProjectID
from models_library.projects_state import RUNNING_STATE_COMPLETED_STATES
from models_library.rabbitmq_messages import (
    ComputationalPipelineStatusMessage,
    EventRabbitMessage,
    LoggerRabbitMessage,
    ProgressRabbitMessageNode,
    ProgressRabbitMessageProject,
    ProgressType,
    WalletCreditsMessage,
    WebserverInternalEventRabbitMessage,
    WebserverInternalEventRabbitMessageAction,
)
from models_library.socketio import SocketMessageDict
from pydantic import TypeAdapter
from servicelib.logging_utils import log_catch, log_context
from servicelib.rabbitmq import RabbitMQClient
from servicelib.utils import limited_gather, logged_gather
from simcore_sdk.node_ports_common.exceptions import ProjectNotFoundError

from ..projects import _nodes_service, _projects_service
from ..rabbitmq import get_rabbitmq_client
from ..socketio.messages import (
    SOCKET_IO_EVENT,
    SOCKET_IO_LOG_EVENT,
    SOCKET_IO_WALLET_OSPARC_CREDITS_UPDATED_EVENT,
    send_message_to_project_room,
    send_message_to_standard_group,
    send_message_to_user,
)
from ..socketio.models import WebSocketNodeProgress, WebSocketProjectProgress
from ..wallets import api as wallets_service
from . import project_logs
from ._rabbitmq_consumers_common import SubscribeArgumentsTuple, subscribe_to_rabbitmq

_logger = logging.getLogger(__name__)

_RABBITMQ_CONSUMERS_APPKEY: Final = web.AppKey("RABBITMQ_CONSUMERS", MutableMapping)
WALLET_SUBSCRIPTIONS_COUNT_APPKEY: Final = web.AppKey(
    "WALLET_SUBSCRIPTIONS_COUNT",
    defaultdict,  # wallet_id -> subscriber count
)
WALLET_SUBSCRIPTION_LOCK_APPKEY: Final = web.AppKey("WALLET_SUBSCRIPTION_LOCK", asyncio.Lock)


async def _notify_comp_node_progress(app: web.Application, message: ProgressRabbitMessageNode) -> None:
    project = await _projects_service.get_project_for_user(
        app, f"{message.project_id}", message.user_id, include_state=True
    )
    await _projects_service.notify_project_node_update(app, project, message.node_id, None)


async def _progress_message_parser(app: web.Application, data: bytes) -> bool:
    rabbit_message: ProgressRabbitMessageNode | ProgressRabbitMessageProject = TypeAdapter(
        ProgressRabbitMessageNode | ProgressRabbitMessageProject
    ).validate_json(data)
    message: SocketMessageDict | None = None
    if isinstance(rabbit_message, ProgressRabbitMessageProject):
        message = WebSocketProjectProgress.from_rabbit_message(rabbit_message).to_socket_dict()
    elif rabbit_message.progress_type is ProgressType.COMPUTATION_RUNNING:
        await _notify_comp_node_progress(app, rabbit_message)
    else:
        message = WebSocketNodeProgress.from_rabbit_message(rabbit_message).to_socket_dict()

    if message:
        await send_message_to_project_room(
            app,
            project_id=rabbit_message.project_id,
            message=message,
        )
    return True


def _is_computational_node(node_key: str) -> bool:
    return "/comp/" in node_key


async def _computational_pipeline_status_message_parser(app: web.Application, data: bytes) -> bool:
    rabbit_message = ComputationalPipelineStatusMessage.model_validate_json(data)
    try:
        project = await _projects_service.get_project_for_user(
            app,
            f"{rabbit_message.project_id}",
            rabbit_message.user_id,
            include_state=True,
        )
    except ProjectNotFoundError:
        _logger.warning(
            "Cannot notify user %s about project %s status: project not found",
            rabbit_message.user_id,
            rabbit_message.project_id,
        )
        return True  # <-- telling RabbitMQ that message was processed

    if rabbit_message.run_result in RUNNING_STATE_COMPLETED_STATES:
        # the pipeline finished, the frontend needs to update all computational nodes
        computational_node_ids = (
            n.node_id
            for n in await _nodes_service.get_project_nodes(app, project_uuid=project["uuid"])
            if _is_computational_node(n.key)
        )
        await limited_gather(
            *[
                _projects_service.notify_project_node_update(app, project, n_id, errors=None)
                for n_id in computational_node_ids
            ],
            limit=10,  # notify 10 nodes at a time
        )
    await _projects_service.notify_project_state_update(app, project)

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
    )
    return True


async def _webserver_internal_events_message_parser(app: web.Application, data: bytes) -> bool:
    """
    Handles internal webserver events that need to be propagated to other webserver replicas

    Ex. Log unsubscription is triggered by user closing a project, which is a REST API call
    that can reach any webserver replica. Then this event is propagated to all replicas
    so that the one holding the websocket connection can unsubscribe from the logs queue.
    """

    rabbit_message = WebserverInternalEventRabbitMessage.model_validate_json(data)

    if rabbit_message.action == WebserverInternalEventRabbitMessageAction.UNSUBSCRIBE_FROM_PROJECT_LOGS_RABBIT_QUEUE:
        _project_id = rabbit_message.data.get("project_id")

        if _project_id:
            _logger.debug(
                "Received UNSUBSCRIBE_FROM_PROJECT_LOGS_RABBIT_QUEUE event for project %s",
                _project_id,
            )
            await project_logs.unsubscribe(app, ProjectID(_project_id))
        else:
            _logger.error(
                "Missing project_id in UNSUBSCRIBE_FROM_PROJECT_LOGS_RABBIT_QUEUE event, this should never happen, investigate!"
            )

    else:
        _logger.warning("Unknown webserver internal event message action %s", rabbit_message.action)

    return True


async def _osparc_credits_message_parser(app: web.Application, data: bytes) -> bool:
    rabbit_message = TypeAdapter(WalletCreditsMessage).validate_json(data)
    wallet_groups = await wallets_service.list_wallet_groups_with_read_access_by_wallet(
        app, wallet_id=rabbit_message.wallet_id
    )
    rooms_to_notify: Generator[GroupID] = (item.gid for item in wallet_groups)
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


_EXCHANGE_TO_PARSER_CONFIG: Final[tuple[SubscribeArgumentsTuple, ...]] = (
    SubscribeArgumentsTuple(
        LoggerRabbitMessage.get_channel_name(),
        _log_message_parser,
        {"topics": []},
    ),
    SubscribeArgumentsTuple(
        ProgressRabbitMessageNode.get_channel_name(),
        _progress_message_parser,
        {"topics": []},
    ),
    SubscribeArgumentsTuple(
        EventRabbitMessage.get_channel_name(),
        _events_message_parser,
        {},
    ),
    SubscribeArgumentsTuple(
        WebserverInternalEventRabbitMessage.get_channel_name(),
        _webserver_internal_events_message_parser,
        {},
    ),
    SubscribeArgumentsTuple(
        WalletCreditsMessage.get_channel_name(),
        _osparc_credits_message_parser,
        {"topics": []},
    ),
    SubscribeArgumentsTuple(
        ComputationalPipelineStatusMessage.get_channel_name(),
        _computational_pipeline_status_message_parser,
        {"topics": []},
    ),
)


async def _unsubscribe_from_rabbitmq(app) -> None:
    with (
        log_context(_logger, logging.INFO, msg="Unsubscribing from rabbitmq channels"),
        log_catch(_logger, reraise=False),
    ):
        rabbit_client: RabbitMQClient = get_rabbitmq_client(app)
        await logged_gather(
            *(rabbit_client.unsubscribe(queue_name) for queue_name, _ in app[_RABBITMQ_CONSUMERS_APPKEY].values()),
        )


async def on_cleanup_ctx_rabbitmq_consumers(
    app: web.Application,
) -> AsyncIterator[None]:
    app[_RABBITMQ_CONSUMERS_APPKEY] = await subscribe_to_rabbitmq(app, _EXCHANGE_TO_PARSER_CONFIG)

    app[WALLET_SUBSCRIPTIONS_COUNT_APPKEY] = defaultdict(
        int
        # wallet_id -> subscriber count
    )
    app[WALLET_SUBSCRIPTION_LOCK_APPKEY] = asyncio.Lock(
        # Ensures exclusive access to wallet subscription changes
    )

    yield

    # cleanup
    await _unsubscribe_from_rabbitmq(app)
