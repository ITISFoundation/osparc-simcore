# pylint: disable=too-many-arguments
import logging

from models_library.api_schemas_directorv2 import (
    DIRECTOR_V2_RPC_NAMESPACE,
)
from models_library.api_schemas_directorv2.computations import TaskLogFileIdGet
from models_library.projects import ProjectID
from models_library.rabbitmq_basic_types import RPCMethodName
from pydantic import TypeAdapter

from ....logging_utils import log_decorator
from ... import RabbitMQRPCClient

_logger = logging.getLogger(__name__)


_RPC_METHOD_NAME_ADAPTER: TypeAdapter[RPCMethodName] = TypeAdapter(RPCMethodName)


@log_decorator(_logger, level=logging.DEBUG)
async def get_computation_task_log_file_ids(
    rabbitmq_rpc_client: RabbitMQRPCClient, *, project_id: ProjectID
) -> list[TaskLogFileIdGet]:
    """
    Raises:
        ComputationalRunNotFoundError
    """
    result = await rabbitmq_rpc_client.request(
        DIRECTOR_V2_RPC_NAMESPACE,
        _RPC_METHOD_NAME_ADAPTER.validate_python("get_computation_task_log_file_ids"),
        project_id=project_id,
    )
    assert isinstance(result, list)  # nosec
    assert all(isinstance(item, TaskLogFileIdGet) for item in result)  # nosec
    return result
