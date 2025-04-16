# pylint: disable=too-many-arguments
import logging
from typing import Final

from models_library.api_schemas_directorv2 import (
    DIRECTOR_V2_RPC_NAMESPACE,
)
from models_library.api_schemas_directorv2.comp_runs import (
    ComputationRunRpcGetPage,
    ComputationTaskRpcGetPage,
)
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.rabbitmq_basic_types import RPCMethodName
from models_library.rest_ordering import OrderBy
from models_library.users import UserID
from pydantic import NonNegativeInt, TypeAdapter

from ....logging_utils import log_decorator
from ... import RabbitMQRPCClient

_logger = logging.getLogger(__name__)


_DEFAULT_TIMEOUT_S: Final[NonNegativeInt] = 20

_RPC_METHOD_NAME_ADAPTER: TypeAdapter[RPCMethodName] = TypeAdapter(RPCMethodName)


@log_decorator(_logger, level=logging.DEBUG)
async def list_computations_latest_iteration_page(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    product_name: ProductName,
    user_id: UserID,
    # pagination
    offset: int = 0,
    limit: int = 20,
    # ordering
    order_by: OrderBy | None = None,
) -> ComputationRunRpcGetPage:
    result = await rabbitmq_rpc_client.request(
        DIRECTOR_V2_RPC_NAMESPACE,
        _RPC_METHOD_NAME_ADAPTER.validate_python(
            "list_computations_latest_iteration_page"
        ),
        product_name=product_name,
        user_id=user_id,
        offset=offset,
        limit=limit,
        order_by=order_by,
        timeout_s=_DEFAULT_TIMEOUT_S,
    )
    assert isinstance(result, ComputationRunRpcGetPage)  # nosec
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def list_computations_latest_iteration_tasks_page(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    product_name: ProductName,
    user_id: UserID,
    project_id: ProjectID,
    # pagination
    offset: int = 0,
    limit: int = 20,
    # ordering
    order_by: OrderBy | None = None,
) -> ComputationTaskRpcGetPage:
    result = await rabbitmq_rpc_client.request(
        DIRECTOR_V2_RPC_NAMESPACE,
        _RPC_METHOD_NAME_ADAPTER.validate_python(
            "list_computations_latest_iteration_tasks_page"
        ),
        product_name=product_name,
        user_id=user_id,
        project_id=project_id,
        offset=offset,
        limit=limit,
        order_by=order_by,
        timeout_s=_DEFAULT_TIMEOUT_S,
    )
    assert isinstance(result, ComputationTaskRpcGetPage)  # nosec
    return result
