import logging

from models_library.api_schemas_webserver import WEBSERVER_RPC_NAMESPACE
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
from models_library.rest_pagination import PageMetaInfoLimitOffset
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
    result: Function = await rabbitmq_rpc_client.request(
        WEBSERVER_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("register_function"),
        function=function,
    )
    TypeAdapter(Function).validate_python(result)  # Validates the result as a Function
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def get_function(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    function_id: FunctionID,
) -> Function:
    result: Function = await rabbitmq_rpc_client.request(
        WEBSERVER_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("get_function"),
        function_id=function_id,
    )
    TypeAdapter(Function).validate_python(result)
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def get_function_input_schema(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    function_id: FunctionID,
) -> FunctionInputSchema:
    result: FunctionInputSchema = await rabbitmq_rpc_client.request(
        WEBSERVER_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("get_function_input_schema"),
        function_id=function_id,
    )
    TypeAdapter(FunctionInputSchema).validate_python(result)
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def get_function_output_schema(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    function_id: FunctionID,
) -> FunctionOutputSchema:
    result: FunctionOutputSchema = await rabbitmq_rpc_client.request(
        WEBSERVER_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("get_function_output_schema"),
        function_id=function_id,
    )
    TypeAdapter(FunctionOutputSchema).validate_python(result)
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def delete_function(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    function_id: FunctionID,
) -> None:
    result: None = await rabbitmq_rpc_client.request(
        WEBSERVER_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("delete_function"),
        function_id=function_id,
    )
    assert result is None  # nosec
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def list_functions(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    pagination_limit: int,
    pagination_offset: int,
) -> tuple[list[Function], PageMetaInfoLimitOffset]:
    result: tuple[list[Function], PageMetaInfoLimitOffset] = (
        await rabbitmq_rpc_client.request(
            WEBSERVER_RPC_NAMESPACE,
            TypeAdapter(RPCMethodName).validate_python("list_functions"),
            pagination_offset=pagination_offset,
            pagination_limit=pagination_limit,
        )
    )
    assert isinstance(result, tuple)
    TypeAdapter(list[Function]).validate_python(
        result[0]
    )  # Validates the result as a list of Functions
    assert isinstance(result[1], PageMetaInfoLimitOffset)  # nosec
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def list_function_jobs(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    pagination_limit: int,
    pagination_offset: int,
) -> tuple[list[FunctionJob], PageMetaInfoLimitOffset]:
    result: tuple[list[FunctionJob], PageMetaInfoLimitOffset] = (
        await rabbitmq_rpc_client.request(
            WEBSERVER_RPC_NAMESPACE,
            TypeAdapter(RPCMethodName).validate_python("list_function_jobs"),
            pagination_offset=pagination_offset,
            pagination_limit=pagination_limit,
        )
    )
    assert isinstance(result, tuple)
    TypeAdapter(list[FunctionJob]).validate_python(
        result[0]
    )  # Validates the result as a list of FunctionJobs
    assert isinstance(result[1], PageMetaInfoLimitOffset)  # nosec
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def list_function_job_collections(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    pagination_limit: int,
    pagination_offset: int,
) -> tuple[list[FunctionJobCollection], PageMetaInfoLimitOffset]:
    result: tuple[list[FunctionJobCollection], PageMetaInfoLimitOffset] = (
        await rabbitmq_rpc_client.request(
            WEBSERVER_RPC_NAMESPACE,
            TypeAdapter(RPCMethodName).validate_python("list_function_job_collections"),
            pagination_offset=pagination_offset,
            pagination_limit=pagination_limit,
        )
    )
    assert isinstance(result, tuple)
    TypeAdapter(list[FunctionJobCollection]).validate_python(
        result[0]
    )  # Validates the result as a list of FunctionJobCollections
    assert isinstance(result[1], PageMetaInfoLimitOffset)  # nosec
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def run_function(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    function_id: FunctionID,
    inputs: FunctionInputs,
) -> FunctionJob:
    result: FunctionJob = await rabbitmq_rpc_client.request(
        WEBSERVER_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("run_function"),
        function_id=function_id,
        inputs=inputs,
    )
    TypeAdapter(FunctionJob).validate_python(
        result
    )  # Validates the result as a FunctionJob
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def register_function_job(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    function_job: FunctionJob,
) -> FunctionJob:
    result: FunctionJob = await rabbitmq_rpc_client.request(
        WEBSERVER_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("register_function_job"),
        function_job=function_job,
    )
    TypeAdapter(FunctionJob).validate_python(
        result
    )  # Validates the result as a FunctionJob
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def get_function_job(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    function_job_id: FunctionJobID,
) -> FunctionJob:
    result: FunctionJob = await rabbitmq_rpc_client.request(
        WEBSERVER_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("get_function_job"),
        function_job_id=function_job_id,
    )

    TypeAdapter(FunctionJob).validate_python(result)
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def delete_function_job(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    function_job_id: FunctionJobID,
) -> None:
    result: None = await rabbitmq_rpc_client.request(
        WEBSERVER_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("delete_function_job"),
        function_job_id=function_job_id,
    )
    assert result is None  # nosec
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def find_cached_function_job(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    function_id: FunctionID,
    inputs: FunctionInputs,
) -> FunctionJob | None:
    result: FunctionJob = await rabbitmq_rpc_client.request(
        WEBSERVER_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("find_cached_function_job"),
        function_id=function_id,
        inputs=inputs,
    )
    if result is None:
        return None
    TypeAdapter(FunctionJob).validate_python(result)
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def register_function_job_collection(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    function_job_collection: FunctionJobCollection,
) -> FunctionJobCollection:
    result: FunctionJobCollection = await rabbitmq_rpc_client.request(
        WEBSERVER_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("register_function_job_collection"),
        function_job_collection=function_job_collection,
    )
    TypeAdapter(FunctionJobCollection).validate_python(result)
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def get_function_job_collection(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    function_job_collection_id: FunctionJobCollectionID,
) -> FunctionJobCollection:
    result: FunctionJobCollection = await rabbitmq_rpc_client.request(
        WEBSERVER_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("get_function_job_collection"),
        function_job_collection_id=function_job_collection_id,
    )
    TypeAdapter(FunctionJobCollection).validate_python(result)
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def delete_function_job_collection(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    function_job_collection_id: FunctionJobCollectionID,
) -> None:
    result: None = await rabbitmq_rpc_client.request(
        WEBSERVER_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("delete_function_job_collection"),
        function_job_collection_id=function_job_collection_id,
    )
    assert result is None
    return result
