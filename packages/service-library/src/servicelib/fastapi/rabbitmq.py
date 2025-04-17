import logging
import warnings

from fastapi import FastAPI
from models_library.rabbitmq_messages import RabbitMessageBase
from settings_library.rabbit import RabbitSettings

from ..rabbitmq import RabbitMQClient
from ..rabbitmq._utils import wait_till_rabbitmq_responsive
from .errors import ApplicationStateError

_logger = logging.getLogger(__name__)


def _create_client(app: FastAPI):
    app.state.rabbitmq_client = RabbitMQClient(
        client_name=app.state.rabbitmq_client_name,
        settings=app.state.rabbitmq_settings,
    )


async def _remove_client(app: FastAPI):
    await app.state.rabbitmq_client.close()
    app.state.rabbitmq_client = None


async def connect(app: FastAPI):
    assert app.state.rabbitmq_settings  # nosec
    await wait_till_rabbitmq_responsive(app.state.rabbitmq_settings.dsn)
    _create_client(app)


async def disconnect(app: FastAPI):
    if app.state.rabbitmq_client:
        await _remove_client(app)


async def reconnect(app: FastAPI):
    await disconnect(app)
    await connect(app)


def setup_rabbit(
    app: FastAPI,
    *,
    settings: RabbitSettings,
    name: str,
) -> None:
    """Sets up rabbit in a given app

    - Inits app.states for rabbitmq
    - Creates a client to communicate with rabbitmq

    Arguments:
        app -- fastapi app
        settings -- Rabbit settings or if None, the connection to rabbit is not done upon startup
        name -- name for the rmq client name
    """
    warnings.warn(
        "The 'setup_rabbit' function is deprecated and will be removed in a future release. "
        "Please use 'rabbitmq_lifespan' for managing RabbitMQ connections.",
        DeprecationWarning,
        stacklevel=2,
    )

    app.state.rabbitmq_client = None  # RabbitMQClient | None
    app.state.rabbitmq_client_name = name
    app.state.rabbitmq_settings = settings

    async def on_startup() -> None:
        await connect(app)

    app.add_event_handler("startup", on_startup)

    async def on_shutdown() -> None:
        await disconnect(app)

    app.add_event_handler("shutdown", on_shutdown)


def get_rabbitmq_client(app: FastAPI) -> RabbitMQClient:
    if not app.state.rabbitmq_client:
        raise ApplicationStateError(
            state="rabbitmq_client",
            msg="Rabbitmq service unavailable. Check app settings",
        )
    assert isinstance(rabbitmq_client := app.state.rabbitmq_client, RabbitMQClient)
    return rabbitmq_client


async def post_message(app: FastAPI, message: RabbitMessageBase) -> None:
    await get_rabbitmq_client(app).publish(message.channel_name, message)
