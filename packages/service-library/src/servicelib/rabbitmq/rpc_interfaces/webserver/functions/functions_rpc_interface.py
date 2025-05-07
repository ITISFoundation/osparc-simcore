import logging

from models_library.api_schemas_webserver import (
    WEBSERVER_RPC_NAMESPACE,
)
from models_library.api_schemas_webserver.functions_wb_schema import (
    Function,
    FunctionID,
    FunctionInputs,
    FunctionInputSchema,
    FunctionJob,
    FunctionJobCollection,
    FunctionJobCollectionID,
    FunctionJobID,
    FunctionOutputSchema,
)
from models_library.rabbitmq_basic_types import RPCMethodName
from models_library.rest_pagination import (
    PageMetaInfoLimitOffset,
)
from pydantic import TypeAdapter

from .....logging_utils import log_decorator
from .... import RabbitMQRPCClient

_logger = logging.getLogger(__name__)


@log_decorator(_logger, level=logging.DEBUG)
async def register_function(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    function: Function,
) -> Function:
    return await rabbitmq_rpc_client.request(
        WEBSERVER_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("register_function"),
        function=function,
    )


@log_decorator(_logger, level=logging.DEBUG)
async def get_function(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    function_id: FunctionID,
) -> Function:
    return await rabbitmq_rpc_client.request(
        WEBSERVER_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("get_function"),
        function_id=function_id,
    )


@log_decorator(_logger, level=logging.DEBUG)
async def get_function_input_schema(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    function_id: FunctionID,
) -> FunctionInputSchema:
    return await rabbitmq_rpc_client.request(
        WEBSERVER_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("get_function_input_schema"),
        function_id=function_id,
    )


@log_decorator(_logger, level=logging.DEBUG)
async def get_function_output_schema(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    function_id: FunctionID,
) -> FunctionOutputSchema:
    return await rabbitmq_rpc_client.request(
        WEBSERVER_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("get_function_output_schema"),
        function_id=function_id,
    )


@log_decorator(_logger, level=logging.DEBUG)
async def delete_function(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    function_id: FunctionID,
) -> None:
    return await rabbitmq_rpc_client.request(
        WEBSERVER_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("delete_function"),
        function_id=function_id,
    )


@log_decorator(_logger, level=logging.DEBUG)
async def list_functions(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *pagination_limit: int,
    pagination_offset: int,
) -> tuple[list[Function], PageMetaInfoLimitOffset]:
    return await rabbitmq_rpc_client.request(
        WEBSERVER_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("list_functions"),
        pagination_offset=pagination_offset,
        pagination_limit=pagination_limit,
    )


@log_decorator(_logger, level=logging.DEBUG)
async def list_function_jobs(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    pagination_limit: int,
    pagination_offset: int,
) -> tuple[list[FunctionJob], PageMetaInfoLimitOffset]:
    return await rabbitmq_rpc_client.request(
        WEBSERVER_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("list_function_jobs"),
        pagination_offset=pagination_offset,
        pagination_limit=pagination_limit,
    )


@log_decorator(_logger, level=logging.DEBUG)
async def list_function_job_collections(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    pagination_limit: int,
    pagination_offset: int,
) -> tuple[list[FunctionJobCollection], PageMetaInfoLimitOffset]:
    return await rabbitmq_rpc_client.request(
        WEBSERVER_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("list_function_job_collections"),
        pagination_offset=pagination_offset,
        pagination_limit=pagination_limit,
    )


@log_decorator(_logger, level=logging.DEBUG)
async def run_function(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    function_id: FunctionID,
    inputs: FunctionInputs,
) -> FunctionJob:
    return await rabbitmq_rpc_client.request(
        WEBSERVER_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("run_function"),
        function_id=function_id,
        inputs=inputs,
    )


@log_decorator(_logger, level=logging.DEBUG)
async def register_function_job(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    function_job: FunctionJob,
) -> FunctionJob:
    return await rabbitmq_rpc_client.request(
        WEBSERVER_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("register_function_job"),
        function_job=function_job,
    )


@log_decorator(_logger, level=logging.DEBUG)
async def get_function_job(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    function_job_id: FunctionJobID,
) -> FunctionJob:
    return await rabbitmq_rpc_client.request(
        WEBSERVER_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("get_function_job"),
        function_job_id=function_job_id,
    )


@log_decorator(_logger, level=logging.DEBUG)
async def delete_function_job(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    function_job_id: FunctionJobID,
) -> None:
    return await rabbitmq_rpc_client.request(
        WEBSERVER_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("delete_function_job"),
        function_job_id=function_job_id,
    )


@log_decorator(_logger, level=logging.DEBUG)
async def find_cached_function_job(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    function_id: FunctionID,
    inputs: FunctionInputs,
) -> FunctionJob | None:
    return await rabbitmq_rpc_client.request(
        WEBSERVER_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("find_cached_function_job"),
        function_id=function_id,
        inputs=inputs,
    )


@log_decorator(_logger, level=logging.DEBUG)
async def register_function_job_collection(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    function_job_collection: FunctionJobCollection,
) -> FunctionJobCollection:
    return await rabbitmq_rpc_client.request(
        WEBSERVER_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("register_function_job_collection"),
        function_job_collection=function_job_collection,
    )


@log_decorator(_logger, level=logging.DEBUG)
async def get_function_job_collection(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    function_job_collection_id: FunctionJobCollectionID,
) -> FunctionJobCollection:
    return await rabbitmq_rpc_client.request(
        WEBSERVER_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("get_function_job_collection"),
        function_job_collection_id=function_job_collection_id,
    )


@log_decorator(_logger, level=logging.DEBUG)
async def delete_function_job_collection(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    function_job_collection_id: FunctionJobCollectionID,
) -> None:
    return await rabbitmq_rpc_client.request(
        WEBSERVER_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("delete_function_job_collection"),
        function_job_collection_id=function_job_collection_id,
    )
