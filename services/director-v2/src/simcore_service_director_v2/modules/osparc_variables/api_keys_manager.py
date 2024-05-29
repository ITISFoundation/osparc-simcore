import warnings
from datetime import timedelta
from typing import Final, cast
from uuid import uuid5

from fastapi import FastAPI
from models_library.api_schemas_webserver.auth import ApiKeyGet
from models_library.products import ProductName
from models_library.projects_nodes_io import NodeID
from models_library.services import RunID
from models_library.users import UserID
from pydantic import BaseModel, StrBytes
from servicelib.fastapi.app_state import SingletonInAppStateMixin
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.redis import RedisClientSDK, RedisClientsManager
from settings_library.redis import RedisDatabase

from ...utils.base_distributed_identifier import BaseDistributedIdentifierManager
from ..rabbitmq import get_rabbitmq_rpc_client
from ._api_auth_rpc import (
    create_api_key_and_secret,
    delete_api_key_and_secret,
    get_api_key_and_secret,
)

# This entire module, API Keys Manager, is DEPRECATED
_DEPRECATION_MSG: Final = (
    "Use osparc_variables._api_auth interface instead to generate API keys and secrets"
)


_CLEANUP_INTERVAL = timedelta(minutes=5)


class _CleanupContext(BaseModel):
    # used for checking if used
    node_id: NodeID

    # used for removing
    product_name: ProductName
    user_id: UserID


class _APIKeysManager(
    SingletonInAppStateMixin,
    BaseDistributedIdentifierManager[str, ApiKeyGet, _CleanupContext],
):
    app_state_name: str = "api_keys_manager"

    def __init__(self, app: FastAPI, redis_client_sdk: RedisClientSDK) -> None:
        super().__init__(redis_client_sdk, cleanup_interval=_CLEANUP_INTERVAL)
        self.app = app

    @property
    def rpc_client(self) -> RabbitMQRPCClient:
        return get_rabbitmq_rpc_client(self.app)

    @classmethod
    def _deserialize_identifier(cls, raw: str) -> str:
        return raw

    @classmethod
    def _serialize_identifier(cls, identifier: str) -> str:
        return identifier

    @classmethod
    def _deserialize_cleanup_context(cls, raw: StrBytes):
        return _CleanupContext.parse_raw(raw)

    @classmethod
    def _serialize_cleanup_context(cls, cleanup_context: _CleanupContext) -> str:
        return cleanup_context.json()

    async def is_used(self, identifier: str, cleanup_context: _CleanupContext) -> bool:
        _ = identifier
        scheduler: "DynamicSidecarsScheduler" = (  # type:ignore [name-defined] # noqa: F821
            self.app.state.dynamic_sidecar_scheduler
        )
        return bool(scheduler.is_service_tracked(cleanup_context.node_id))

    async def _create(  # type:ignore [override] # pylint:disable=arguments-differ
        self, identifier: str, product_name: ProductName, user_id: UserID
    ) -> tuple[str, ApiKeyGet]:
        result = await create_api_key_and_secret(
            self.app,
            product_name=product_name,
            user_id=user_id,
            name=identifier,
            expiration=None,
        )
        return identifier, ApiKeyGet.parse_obj(result)

    async def get(  # type:ignore [override] # pylint:disable=arguments-differ
        self, identifier: str, product_name: ProductName, user_id: UserID
    ) -> ApiKeyGet | None:
        return await get_api_key_and_secret(
            self.app, product_name=product_name, user_id=user_id, name=identifier
        )

    async def _destroy(self, identifier: str, cleanup_context: _CleanupContext) -> None:
        await delete_api_key_and_secret(
            self.app,
            product_name=cleanup_context.product_name,
            user_id=cleanup_context.user_id,
            name=identifier,
        )


def _get_identifier(node_id: NodeID, run_id: RunID) -> str:
    # Generates a new unique key name for each service run
    # This avoids race conditions if the service is starting and
    # an the cleanup job is removing the key from an old run which
    # was wrongly shut down
    return f"_auto_{uuid5(node_id, run_id)}"


async def _get_or_create(
    app: FastAPI,
    *,
    product_name: ProductName,
    user_id: UserID,
    node_id: NodeID,
    run_id: RunID,
) -> ApiKeyGet:

    warnings.warn(
        _DEPRECATION_MSG,
        category=DeprecationWarning,
        stacklevel=1,
    )

    api_keys_manager: _APIKeysManager = _APIKeysManager.get_from_app_state(app)
    display_name = _get_identifier(node_id, run_id)

    api_key: ApiKeyGet | None = await api_keys_manager.get(
        identifier=display_name,
        product_name=product_name,
        user_id=user_id,
    )
    if api_key is None:
        _, api_key = await api_keys_manager.create(
            cleanup_context=_CleanupContext(
                node_id=node_id, product_name=product_name, user_id=user_id
            ),
            identifier=display_name,
            product_name=product_name,
            user_id=user_id,
        )

    assert display_name == api_key.display_name  # nosec
    return api_key


async def get_or_create_api_key(
    app: FastAPI,
    product_name: ProductName,
    user_id: UserID,
    node_id: NodeID,
    run_id: RunID,
) -> str:
    data = await _get_or_create(
        app,
        product_name=product_name,
        user_id=user_id,
        node_id=node_id,
        run_id=run_id,
    )
    return cast(str, data.api_key)


async def get_or_create_api_secret(
    app: FastAPI,
    product_name: ProductName,
    user_id: UserID,
    node_id: NodeID,
    run_id: RunID,
) -> str:
    data = await _get_or_create(
        app,
        product_name=product_name,
        user_id=user_id,
        node_id=node_id,
        run_id=run_id,
    )
    return cast(str, data.api_secret)


async def safe_remove_api_key_and_secret(
    app: FastAPI, *, node_id: NodeID, run_id: RunID
) -> None:
    # Left active so that registry deletes all generated api-keys deployed
    warnings.warn(
        _DEPRECATION_MSG,
        category=DeprecationWarning,
        stacklevel=1,
    )
    api_keys_manager = _APIKeysManager.get_from_app_state(app)
    display_name = _get_identifier(node_id, run_id)

    await api_keys_manager.remove(identifier=display_name)


def setup(app: FastAPI) -> None:
    async def _on_startup() -> None:
        redis_clients_manager: RedisClientsManager = app.state.redis_clients_manager

        manager = _APIKeysManager(
            app, redis_clients_manager.client(RedisDatabase.DISTRIBUTED_IDENTIFIERS)
        )
        manager.set_to_app_state(app)
        await manager.setup()

    async def _on_shutdown() -> None:
        manager: _APIKeysManager = _APIKeysManager.get_from_app_state(app)
        await manager.shutdown()

    app.add_event_handler("startup", _on_startup)
    app.add_event_handler("shutdown", _on_shutdown)
