from collections.abc import Awaitable, Callable

import orjson
from fastapi import FastAPI
from models_library.api_schemas_webserver.wallets import WalletPaymentCreated
from servicelib.rabbitmq import RabbitMQRPCClient, RPCMethodName
from simcore_service_payments.api.rpc._payments import create_payment
from simcore_service_payments.api.rpc.routes import setup_rpc_routes
from simcore_service_payments.services.rabbitmq import PAYMENTS_RPC_NAMESPACE

pytest_simcore_core_services_selection = [
    "rabbit",
]


async def test_webserver_one_time_payment_workflow(
    app: FastAPI, rabbitmq_rpc_client: Callable[[str], Awaitable[RabbitMQRPCClient]]
):

    setup_rpc_routes(app)

    rpc_client = await rabbitmq_rpc_client("web-server-client")

    kwargs = {
        "amount_dollars": 100,
        "target_credits": 100,
        "product_name": "osparc",
        "wallet_id": 1,
        "wallet_name": "wallet-name",
        "user_id": 1,
        "user_name": "user-name",
        "user_email": "user-name@email.com",
    }

    json_result = await rpc_client.request(
        PAYMENTS_RPC_NAMESPACE, RPCMethodName(create_payment.__name__), **kwargs
    )
    assert isinstance(json_result, bytes)
    result = orjson.loads(json_result)

    WalletPaymentCreated.parse_obj(result)
