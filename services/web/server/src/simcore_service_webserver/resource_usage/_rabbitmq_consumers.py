import functools
import logging
from typing import AsyncIterator

from aiohttp import web
from models_library.rabbitmq_messages import WalletCreditsMessage
from pydantic import parse_raw_as
from servicelib.logging_utils import log_catch, log_context
from servicelib.rabbitmq import RabbitMQClient

from ..rabbitmq import get_rabbitmq_client
from ..socketio.messages import (
    SOCKET_IO_WALLET_OSPARC_CREDITS_UPDATED_EVENT,
    SocketMessageDict,
    send_group_messages,
)
from ..wallets import api as wallets_api
from ._constants import APP_RABBITMQ_CONSUMERS_KEY

_logger = logging.getLogger(__name__)


async def _process_message(app: web.Application, data: bytes) -> bool:
    rabbit_message = parse_raw_as(WalletCreditsMessage, data)
    socket_messages: list[SocketMessageDict] = [
        {
            "event_type": SOCKET_IO_WALLET_OSPARC_CREDITS_UPDATED_EVENT,
            "data": {
                "wallet_id": rabbit_message.wallet_id,
                "osparc_credits": rabbit_message.credits,
                "created_at": rabbit_message.created_at,
            },
        }
    ]
    wallet_groups = await wallets_api.list_wallet_groups_with_read_access_by_wallet(
        app, rabbit_message.wallet_id
    )
    rooms_to_notify = [f"{item.gid}" for item in wallet_groups]
    for room in rooms_to_notify:
        await send_group_messages(app, room, socket_messages)
    return True


async def _subscribe_to_rabbitmq(app) -> str:
    with log_context(_logger, logging.INFO, msg="Subscribing to rabbitmq channel"):
        rabbit_client: RabbitMQClient = get_rabbitmq_client(app)
        subscribed_queue: str = await rabbit_client.subscribe(
            WalletCreditsMessage.get_channel_name(),
            message_handler=functools.partial(_process_message, app),
            topics=[],
        )
        return subscribed_queue


async def _unsubscribe_from_rabbitmq(app) -> None:
    with log_context(
        _logger, logging.INFO, msg="Unsubscribing from rabbitmq channels"
    ), log_catch(_logger, reraise=False):
        rabbit_client: RabbitMQClient = get_rabbitmq_client(app)
        await rabbit_client.unsubscribe(app[APP_RABBITMQ_CONSUMERS_KEY])


async def setup_rabbitmq_consumers(app: web.Application) -> AsyncIterator[None]:
    app[APP_RABBITMQ_CONSUMERS_KEY] = await _subscribe_to_rabbitmq(app)
    yield

    # cleanup
    await _unsubscribe_from_rabbitmq(app)
