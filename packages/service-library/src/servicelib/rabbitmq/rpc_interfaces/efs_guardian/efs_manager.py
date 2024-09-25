import logging
from pathlib import Path
from typing import Final

from models_library.api_schemas_efs_guardian import EFS_GUARDIAN_RPC_NAMESPACE
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.rabbitmq_basic_types import RPCMethodName
from pydantic import NonNegativeInt, TypeAdapter

from ....logging_utils import log_decorator
from ....rabbitmq import RabbitMQRPCClient

_logger = logging.getLogger(__name__)


_DEFAULT_TIMEOUT_S: Final[NonNegativeInt] = 20


@log_decorator(_logger, level=logging.DEBUG)
async def create_project_specific_data_dir(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    project_id: ProjectID,
    node_id: NodeID,
    storage_directory_name: str,
) -> Path:
    output: Path = await rabbitmq_rpc_client.request(
        EFS_GUARDIAN_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("create_project_specific_data_dir"),
        project_id=project_id,
        node_id=node_id,
        storage_directory_name=storage_directory_name,
        timeout_s=_DEFAULT_TIMEOUT_S,
    )
    return output
