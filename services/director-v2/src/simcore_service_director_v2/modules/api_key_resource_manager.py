from uuid import uuid5

from fastapi import FastAPI
from models_library.api_schemas_webserver import WEBSERVER_RPC_NAMESPACE
from models_library.api_schemas_webserver.auth import ApiKeyCreate, ApiKeyGet
from models_library.products import ProductName
from models_library.projects_nodes_io import NodeID
from models_library.rabbitmq_basic_types import RPCMethodName
from models_library.users import UserID
from pydantic import parse_obj_as
from servicelib.osparc_generic_resource import BaseOsparcGenericResourcesManager
from servicelib.rabbitmq import RabbitMQRPCClient

from .rabbitmq import get_rabbitmq_rpc_client


class APIKeysManager(BaseOsparcGenericResourcesManager[str, ApiKeyGet]):
    def __init__(self, app: FastAPI) -> None:
        self.GET_OR_CREATE_INJECTS_IDENTIFIER = True
        self.app = app

    @property
    def rpc_client(self) -> RabbitMQRPCClient:
        return get_rabbitmq_rpc_client(self.app)

    # pylint:disable=arguments-differ

    async def get(
        self, identifier: str, product_name: ProductName, user_id: UserID
    ) -> ApiKeyGet | None:
        result = await self.rpc_client.request(
            WEBSERVER_RPC_NAMESPACE,
            parse_obj_as(RPCMethodName, "api_key_get"),
            product_name=product_name,
            user_id=user_id,
            name=identifier,
        )
        return parse_obj_as(ApiKeyGet | None, result)

    async def create(
        self, identifier: str, product_name: ProductName, user_id: UserID
    ) -> tuple[str, ApiKeyGet]:
        result = await self.rpc_client.request(
            WEBSERVER_RPC_NAMESPACE,
            parse_obj_as(RPCMethodName, "create_api_keys"),
            product_name=product_name,
            user_id=user_id,
            new=ApiKeyCreate(display_name=identifier, expiration=None),
        )
        return identifier, ApiKeyGet.parse_obj(result)

    async def destroy(
        self, identifier: str, product_name: ProductName, user_id: UserID
    ) -> None:
        await self.rpc_client.request(
            WEBSERVER_RPC_NAMESPACE,
            parse_obj_as(RPCMethodName, "delete_api_keys"),
            product_name=product_name,
            user_id=user_id,
            name=identifier,
        )


def get_api_key_name(node_id: NodeID) -> str:
    obfuscated_node_id = uuid5(node_id, f"{node_id}")
    return f"_auto_{obfuscated_node_id}"


def get_api_keys_manager(app: FastAPI) -> APIKeysManager:
    api_keys_manager: APIKeysManager = app.state.api_keys_manager
    return api_keys_manager


def setup(app: FastAPI) -> None:
    async def on_startup() -> None:
        app.state.api_keys_manager = APIKeysManager(app)

    app.add_event_handler("startup", on_startup)
