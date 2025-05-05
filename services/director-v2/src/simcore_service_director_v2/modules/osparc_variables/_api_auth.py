import logging
import uuid
from datetime import timedelta
from uuid import uuid5

from fastapi import FastAPI
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.rpc.webserver.auth.api_keys import generate_unique_api_key
from models_library.users import UserID

from ._api_auth_rpc import create_api_key as rpc_create_api_key
from ._api_auth_rpc import delete_api_key_by_key as rpc_delete_api_key

_EXPIRATION_AUTO_KEYS = timedelta(weeks=4)


_logger = logging.getLogger(__name__)


def create_unique_api_name_for(
    product_name: ProductName,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
) -> str:
    # NOTE: The namespace chosen doesn't significantly impact the resulting UUID
    # as long as it's consistently used across the same context
    return f"__auto_{uuid5(uuid.NAMESPACE_DNS, f'{product_name}/{user_id}/{project_id}/{node_id}')}"


async def create_user_api_key(
    app: FastAPI,  # pylint: disable=unused-argument
    product_name: ProductName,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
) -> str:
    # NOTE: Given the display name, the API key is deterministically generated
    return generate_unique_api_key(
        create_unique_api_name_for(product_name, user_id, project_id, node_id)
    )


async def create_user_api_secret(
    app: FastAPI,
    product_name: ProductName,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
) -> str:
    display_name = create_unique_api_name_for(
        product_name, user_id, project_id, node_id
    )
    _logger.debug("Creating API key for %s", display_name)
    data = await rpc_create_api_key(
        app,
        user_id=user_id,
        product_name=product_name,
        display_name=display_name,
        expiration=_EXPIRATION_AUTO_KEYS,
    )
    assert data.api_secret  # nosec
    assert isinstance(data.api_secret, str)  # nosec
    return data.api_secret


async def delete_api_key_by_key(
    app: FastAPI,
    product_name: ProductName,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
) -> None:
    api_key = create_unique_api_name_for(product_name, user_id, project_id, node_id)
    await rpc_delete_api_key(
        app=app,
        product_name=product_name,
        user_id=user_id,
        api_key=api_key,
    )


__all__: tuple[str, ...] = (
    "create_user_api_key",
    "create_user_api_secret",
    "delete_api_key_by_key",
)
