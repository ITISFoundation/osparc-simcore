import logging

from models_library.api_schemas_webserver import WEBSERVER_RPC_NAMESPACE
from models_library.api_schemas_webserver.projects import ProjectID
from models_library.projects_nodes import Node
from models_library.rabbitmq_basic_types import RPCMethodName
from models_library.rpc.webserver.projects.projects_nodes import ProjectNodeGet
from pydantic import TypeAdapter
from servicelib.logging_utils import log_decorator
from servicelib.rabbitmq import RabbitMQRPCClient

_logger = logging.getLogger(__name__)


@log_decorator(_logger, level=logging.DEBUG)
async def list_project_nodes(
    rpc_client: RabbitMQRPCClient,
    *,
    project_uuid: ProjectID,
) -> list[Node]:
    result: list[ProjectNodeGet] = await rpc_client.request(
        WEBSERVER_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("list_project_nodes"),
        project_uuid=project_uuid,
    )
    return TypeAdapter(list[Node]).validate_python(result)
