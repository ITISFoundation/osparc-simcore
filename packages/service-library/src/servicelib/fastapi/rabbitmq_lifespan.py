import logging
from collections.abc import AsyncIterator
from enum import StrEnum

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State
from settings_library.rabbit import RabbitSettings

from ..logging_utils import log_catch
from ..rabbitmq import RabbitMQClient, RabbitMQRPCClient, wait_till_rabbitmq_responsive
from .lifespan_utils import (
    PublisherLifespan,
    create_publisher_lifespan,
    lifespan_context,
)

_logger = logging.getLogger(__name__)


class _RabbitMQLifespanState(StrEnum):
    RABBITMQ_CLIENT = "rabbitmq.client"
    RABBITMQ_RPC_CLIENT = "rabbitmq.rpc_client"


def _create_rabbitmq_client_lifespan(
    settings: RabbitSettings | None,
    *,
    client_name: str,
    wait_for_connectivity: bool,
) -> PublisherLifespan:
    async def _lifespan(_: FastAPI, state: State) -> AsyncIterator[State]:
        _lifespan_name = f"{__name__}._rabbitmq_client_lifespan[{client_name}]"

        with lifespan_context(_logger, logging.INFO, _lifespan_name, state) as called_state:
            if settings is None:
                yield {
                    _RabbitMQLifespanState.RABBITMQ_CLIENT: None,
                    **called_state,
                }
                return

            if wait_for_connectivity:
                await wait_till_rabbitmq_responsive(settings.dsn)

            rabbitmq_client = RabbitMQClient(client_name=client_name, settings=settings)
            try:
                yield {
                    _RabbitMQLifespanState.RABBITMQ_CLIENT: rabbitmq_client,
                    **called_state,
                }
            finally:
                with log_catch(_logger, reraise=False):
                    await rabbitmq_client.close()

    return _lifespan


def _create_rabbitmq_rpc_client_lifespan(
    settings: RabbitSettings | None,
    *,
    client_name: str,
    wait_for_connectivity: bool,
) -> PublisherLifespan:
    async def _lifespan(_: FastAPI, state: State) -> AsyncIterator[State]:
        _lifespan_name = f"{__name__}._rabbitmq_rpc_client_lifespan[{client_name}]"

        with lifespan_context(_logger, logging.INFO, _lifespan_name, state) as called_state:
            if settings is None:
                yield {
                    _RabbitMQLifespanState.RABBITMQ_RPC_CLIENT: None,
                    **called_state,
                }
                return

            if wait_for_connectivity:
                await wait_till_rabbitmq_responsive(settings.dsn)

            rabbitmq_rpc_client = await RabbitMQRPCClient.create(client_name=client_name, settings=settings)
            try:
                yield {
                    _RabbitMQLifespanState.RABBITMQ_RPC_CLIENT: rabbitmq_rpc_client,
                    **called_state,
                }
            finally:
                with log_catch(_logger, reraise=False):
                    await rabbitmq_rpc_client.close()

    return _lifespan


def configure_rabbitmq_client(
    app_lifespan: LifespanManager[FastAPI],
    *,
    settings: RabbitSettings | None,
    client_name: str,
    app_state_attr: str = "rabbitmq_client",
    wait_for_connectivity: bool = True,
) -> None:
    rabbitmq_lifespan_manager: LifespanManager[FastAPI] = LifespanManager()
    rabbitmq_lifespan_manager.add(
        _create_rabbitmq_client_lifespan(
            settings,
            client_name=client_name,
            wait_for_connectivity=wait_for_connectivity,
        )
    )
    rabbitmq_lifespan_manager.add(
        create_publisher_lifespan(
            state_key=_RabbitMQLifespanState.RABBITMQ_CLIENT,
            app_state_attr=app_state_attr,
        )
    )
    app_lifespan.include(rabbitmq_lifespan_manager)


def configure_rabbitmq_rpc_client(
    app_lifespan: LifespanManager[FastAPI],
    *,
    settings: RabbitSettings | None,
    client_name: str,
    app_state_attr: str = "rabbitmq_rpc_client",
    wait_for_connectivity: bool = True,
) -> None:
    rabbitmq_lifespan_manager: LifespanManager[FastAPI] = LifespanManager()
    rabbitmq_lifespan_manager.add(
        _create_rabbitmq_rpc_client_lifespan(
            settings,
            client_name=client_name,
            wait_for_connectivity=wait_for_connectivity,
        )
    )
    rabbitmq_lifespan_manager.add(
        create_publisher_lifespan(
            state_key=_RabbitMQLifespanState.RABBITMQ_RPC_CLIENT,
            app_state_attr=app_state_attr,
        )
    )
    app_lifespan.include(rabbitmq_lifespan_manager)
