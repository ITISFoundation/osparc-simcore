import logging
from typing import Final

from models_library.api_schemas_efs_guardian import EFS_GUARDIAN_RPC_NAMESPACE
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.rabbitmq_basic_types import RPCMethodName
from pydantic import NonNegativeInt, parse_obj_as

from ....logging_utils import log_decorator
from ....rabbitmq import RabbitMQRPCClient

_logger = logging.getLogger(__name__)


_DEFAULT_TIMEOUT_S: Final[NonNegativeInt] = 20


@log_decorator(_logger, level=logging.DEBUG)
async def get_pricing_plan(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    project_id: ProjectID,
    node_id: NodeID,
) -> None:
    await rabbitmq_rpc_client.request(
        EFS_GUARDIAN_RPC_NAMESPACE,
        parse_obj_as(RPCMethodName, "create_project_specific_data_dir"),
        project_id=project_id,
        node_id=node_id,
        timeout_s=_DEFAULT_TIMEOUT_S,
    )
