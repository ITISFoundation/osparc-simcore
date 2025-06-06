import logging

from models_library.api_schemas_webserver import WEBSERVER_RPC_NAMESPACE
from models_library.api_schemas_webserver.functions import (
    Function,
    FunctionID,
    FunctionInputs,
    FunctionInputSchema,
    FunctionJob,
    FunctionJobCollection,
    FunctionJobCollectionID,
    FunctionJobCollectionsListFilters,
    FunctionJobID,
    FunctionOutputSchema,
    RegisteredFunction,
    RegisteredFunctionJob,
    RegisteredFunctionJobCollection,
)
from models_library.functions import FunctionUserAccessRights
from models_library.products import ProductName
from models_library.rabbitmq_basic_types import RPCMethodName
from models_library.rest_pagination import PageMetaInfoLimitOffset
from models_library.users import UserID
from pydantic import TypeAdapter

from .....logging_utils import log_decorator
from .... import RabbitMQRPCClient

_logger = logging.getLogger(__name__)


@log_decorator(_logger, level=logging.DEBUG)
async def register_function(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    user_id: UserID,
    product_name: ProductName,
    function: Function,
) -> RegisteredFunction:
    result = await rabbitmq_rpc_client.request(
        WEBSERVER_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("register_function"),
        function=function,
        user_id=user_id,
        product_name=product_name,
    )
    return TypeAdapter(RegisteredFunction).validate_python(
        result
    )  # Validates the result as a RegisteredFunction


@log_decorator(_logger, level=logging.DEBUG)
async def get_function(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_id: FunctionID,
) -> RegisteredFunction:
    result = await rabbitmq_rpc_client.request(
        WEBSERVER_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("get_function"),
        function_id=function_id,
        user_id=user_id,
        product_name=product_name,
    )
    return TypeAdapter(RegisteredFunction).validate_python(result)


@log_decorator(_logger, level=logging.DEBUG)
async def get_function_input_schema(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    function_id: FunctionID,
    user_id: UserID,
    product_name: ProductName,
) -> FunctionInputSchema:
    result = await rabbitmq_rpc_client.request(
        WEBSERVER_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("get_function_input_schema"),
        function_id=function_id,
        user_id=user_id,
        product_name=product_name,
    )
    return TypeAdapter(FunctionInputSchema).validate_python(result)


@log_decorator(_logger, level=logging.DEBUG)
async def get_function_output_schema(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    function_id: FunctionID,
    user_id: UserID,
    product_name: ProductName,
) -> FunctionOutputSchema:
    result = await rabbitmq_rpc_client.request(
        WEBSERVER_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("get_function_output_schema"),
        function_id=function_id,
        user_id=user_id,
        product_name=product_name,
    )
    return TypeAdapter(FunctionOutputSchema).validate_python(result)


@log_decorator(_logger, level=logging.DEBUG)
async def delete_function(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    function_id: FunctionID,
    user_id: UserID,
    product_name: ProductName,
) -> None:
    result = await rabbitmq_rpc_client.request(
        WEBSERVER_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("delete_function"),
        function_id=function_id,
        user_id=user_id,
        product_name=product_name,
    )
    assert result is None  # nosec
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def list_functions(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    user_id: UserID,
    product_name: ProductName,
    pagination_offset: int,
    pagination_limit: int,
) -> tuple[list[RegisteredFunction], PageMetaInfoLimitOffset]:
    result: tuple[list[RegisteredFunction], PageMetaInfoLimitOffset] = (
        await rabbitmq_rpc_client.request(
            WEBSERVER_RPC_NAMESPACE,
            TypeAdapter(RPCMethodName).validate_python("list_functions"),
            pagination_offset=pagination_offset,
            pagination_limit=pagination_limit,
            user_id=user_id,
            product_name=product_name,
        )
    )
    return TypeAdapter(
        tuple[list[RegisteredFunction], PageMetaInfoLimitOffset]
    ).validate_python(result)


@log_decorator(_logger, level=logging.DEBUG)
async def list_function_jobs(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    user_id: UserID,
    product_name: ProductName,
    pagination_limit: int,
    pagination_offset: int,
    filter_by_function_id: FunctionID | None = None,
) -> tuple[list[RegisteredFunctionJob], PageMetaInfoLimitOffset]:
    result: tuple[list[RegisteredFunctionJob], PageMetaInfoLimitOffset] = (
        await rabbitmq_rpc_client.request(
            WEBSERVER_RPC_NAMESPACE,
            TypeAdapter(RPCMethodName).validate_python("list_function_jobs"),
            user_id=user_id,
            product_name=product_name,
            pagination_offset=pagination_offset,
            pagination_limit=pagination_limit,
            filter_by_function_id=filter_by_function_id,
        )
    )
    return TypeAdapter(
        tuple[list[RegisteredFunctionJob], PageMetaInfoLimitOffset]
    ).validate_python(result)


@log_decorator(_logger, level=logging.DEBUG)
async def list_function_job_collections(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    user_id: UserID,
    product_name: ProductName,
    pagination_limit: int,
    pagination_offset: int,
    filters: FunctionJobCollectionsListFilters | None = None,
) -> tuple[list[RegisteredFunctionJobCollection], PageMetaInfoLimitOffset]:
    result = await rabbitmq_rpc_client.request(
        WEBSERVER_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("list_function_job_collections"),
        pagination_offset=pagination_offset,
        pagination_limit=pagination_limit,
        filters=filters,
        user_id=user_id,
        product_name=product_name,
    )
    return TypeAdapter(
        tuple[list[RegisteredFunctionJobCollection], PageMetaInfoLimitOffset]
    ).validate_python(result)


@log_decorator(_logger, level=logging.DEBUG)
async def update_function_title(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_id: FunctionID,
    title: str,
) -> RegisteredFunction:
    result = await rabbitmq_rpc_client.request(
        WEBSERVER_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("update_function_title"),
        function_id=function_id,
        title=title,
        user_id=user_id,
        product_name=product_name,
    )
    return TypeAdapter(RegisteredFunction).validate_python(result)


@log_decorator(_logger, level=logging.DEBUG)
async def update_function_description(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_id: FunctionID,
    description: str,
) -> RegisteredFunction:
    result = await rabbitmq_rpc_client.request(
        WEBSERVER_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("update_function_description"),
        function_id=function_id,
        description=description,
        user_id=user_id,
        product_name=product_name,
    )
    return TypeAdapter(RegisteredFunction).validate_python(result)


@log_decorator(_logger, level=logging.DEBUG)
async def run_function(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    function_id: FunctionID,
    inputs: FunctionInputs,
    user_id: UserID,
    product_name: ProductName,
) -> RegisteredFunctionJob:
    result = await rabbitmq_rpc_client.request(
        WEBSERVER_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("run_function"),
        function_id=function_id,
        inputs=inputs,
        user_id=user_id,
        product_name=product_name,
    )
    return TypeAdapter(RegisteredFunctionJob).validate_python(
        result
    )  # Validates the result as a RegisteredFunctionJob


@log_decorator(_logger, level=logging.DEBUG)
async def register_function_job(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_job: FunctionJob,
) -> RegisteredFunctionJob:
    result = await rabbitmq_rpc_client.request(
        WEBSERVER_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("register_function_job"),
        function_job=function_job,
        user_id=user_id,
        product_name=product_name,
    )
    return TypeAdapter(RegisteredFunctionJob).validate_python(
        result
    )  # Validates the result as a RegisteredFunctionJob


@log_decorator(_logger, level=logging.DEBUG)
async def get_function_job(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    user_id: UserID,
    function_job_id: FunctionJobID,
    product_name: ProductName,
) -> RegisteredFunctionJob:
    result = await rabbitmq_rpc_client.request(
        WEBSERVER_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("get_function_job"),
        function_job_id=function_job_id,
        user_id=user_id,
        product_name=product_name,
    )

    return TypeAdapter(RegisteredFunctionJob).validate_python(result)


@log_decorator(_logger, level=logging.DEBUG)
async def delete_function_job(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_job_id: FunctionJobID,
) -> None:
    result: None = await rabbitmq_rpc_client.request(
        WEBSERVER_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("delete_function_job"),
        function_job_id=function_job_id,
        user_id=user_id,
        product_name=product_name,
    )
    assert result is None  # nosec


@log_decorator(_logger, level=logging.DEBUG)
async def find_cached_function_jobs(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_id: FunctionID,
    inputs: FunctionInputs,
) -> list[RegisteredFunctionJob] | None:
    result = await rabbitmq_rpc_client.request(
        WEBSERVER_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("find_cached_function_jobs"),
        function_id=function_id,
        inputs=inputs,
        user_id=user_id,
        product_name=product_name,
    )
    if result is None:
        return None
    return TypeAdapter(list[RegisteredFunctionJob]).validate_python(result)


@log_decorator(_logger, level=logging.DEBUG)
async def register_function_job_collection(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_job_collection: FunctionJobCollection,
) -> RegisteredFunctionJobCollection:
    result = await rabbitmq_rpc_client.request(
        WEBSERVER_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("register_function_job_collection"),
        function_job_collection=function_job_collection,
        user_id=user_id,
        product_name=product_name,
    )
    return TypeAdapter(RegisteredFunctionJobCollection).validate_python(result)


@log_decorator(_logger, level=logging.DEBUG)
async def get_function_job_collection(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    user_id: UserID,
    function_job_collection_id: FunctionJobCollectionID,
    product_name: ProductName,
) -> RegisteredFunctionJobCollection:
    result = await rabbitmq_rpc_client.request(
        WEBSERVER_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("get_function_job_collection"),
        function_job_collection_id=function_job_collection_id,
        user_id=user_id,
        product_name=product_name,
    )
    return TypeAdapter(RegisteredFunctionJobCollection).validate_python(result)


@log_decorator(_logger, level=logging.DEBUG)
async def delete_function_job_collection(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_job_collection_id: FunctionJobCollectionID,
) -> None:
    result = await rabbitmq_rpc_client.request(
        WEBSERVER_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("delete_function_job_collection"),
        function_job_collection_id=function_job_collection_id,
        user_id=user_id,
        product_name=product_name,
    )
    assert result is None  # nosec


@log_decorator(_logger, level=logging.DEBUG)
async def get_function_user_permissions(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_id: FunctionID,
) -> FunctionUserAccessRights:
    result = await rabbitmq_rpc_client.request(
        WEBSERVER_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("get_function_user_permissions"),
        function_id=function_id,
        user_id=user_id,
        product_name=product_name,
    )
    return TypeAdapter(FunctionUserAccessRights).validate_python(result)
