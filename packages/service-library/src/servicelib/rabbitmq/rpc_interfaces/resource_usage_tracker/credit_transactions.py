import logging
from decimal import Decimal
from typing import Final

from models_library.api_schemas_resource_usage_tracker import (
    RESOURCE_USAGE_TRACKER_RPC_NAMESPACE,
)
from models_library.api_schemas_resource_usage_tracker.credit_transactions import (
    CreditTransactionCreateBody,
    WalletTotalCredits,
)
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.rabbitmq_basic_types import RPCMethodName
from models_library.resource_tracker import CreditTransactionStatus
from models_library.services_types import ServiceRunID
from models_library.wallets import WalletID
from pydantic import NonNegativeInt, TypeAdapter

from ....logging_utils import log_decorator
from ....rabbitmq import RabbitMQRPCClient

_logger = logging.getLogger(__name__)


_DEFAULT_TIMEOUT_S: Final[NonNegativeInt] = 20

_RPC_METHOD_NAME_ADAPTER: TypeAdapter[RPCMethodName] = TypeAdapter(RPCMethodName)


@log_decorator(_logger, level=logging.DEBUG)
async def get_wallet_total_credits(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    product_name: ProductName,
    wallet_id: WalletID,
) -> WalletTotalCredits:
    result = await rabbitmq_rpc_client.request(
        RESOURCE_USAGE_TRACKER_RPC_NAMESPACE,
        _RPC_METHOD_NAME_ADAPTER.validate_python("get_wallet_total_credits"),
        product_name=product_name,
        wallet_id=wallet_id,
        timeout_s=_DEFAULT_TIMEOUT_S,
    )
    assert isinstance(result, WalletTotalCredits)  # nosec
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def get_project_wallet_total_credits(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    product_name: ProductName,
    wallet_id: WalletID,
    project_id: ProjectID,
    transaction_status: CreditTransactionStatus | None = None,
) -> WalletTotalCredits:
    result = await rabbitmq_rpc_client.request(
        RESOURCE_USAGE_TRACKER_RPC_NAMESPACE,
        _RPC_METHOD_NAME_ADAPTER.validate_python("get_project_wallet_total_credits"),
        product_name=product_name,
        wallet_id=wallet_id,
        project_id=project_id,
        transaction_status=transaction_status,
        timeout_s=_DEFAULT_TIMEOUT_S,
    )
    assert isinstance(result, WalletTotalCredits)  # nosec
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def pay_project_debt(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    project_id: ProjectID,
    current_wallet_transaction: CreditTransactionCreateBody,
    new_wallet_transaction: CreditTransactionCreateBody,
) -> None:
    await rabbitmq_rpc_client.request(
        RESOURCE_USAGE_TRACKER_RPC_NAMESPACE,
        _RPC_METHOD_NAME_ADAPTER.validate_python("pay_project_debt"),
        project_id=project_id,
        current_wallet_transaction=current_wallet_transaction,
        new_wallet_transaction=new_wallet_transaction,
        timeout_s=_DEFAULT_TIMEOUT_S,
    )


@log_decorator(_logger, level=logging.DEBUG)
async def get_transaction_current_credits_by_service_run_id(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    service_run_id: ServiceRunID,
) -> Decimal:
    result = await rabbitmq_rpc_client.request(
        RESOURCE_USAGE_TRACKER_RPC_NAMESPACE,
        _RPC_METHOD_NAME_ADAPTER.validate_python(
            "get_transaction_current_credits_by_service_run_id"
        ),
        service_run_id=service_run_id,
        timeout_s=_DEFAULT_TIMEOUT_S,
    )
    assert isinstance(result, Decimal)  # nosec
    return result
