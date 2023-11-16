import logging
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from models_library.api_schemas_webserver import WEBSERVER_RPC_NAMESPACE
from models_library.api_schemas_webserver.wallets import GetWalletAutoRecharge
from models_library.products import CreditResultGet
from models_library.rabbitmq_basic_types import RPCMethodName
from models_library.rabbitmq_messages import WalletCreditsMessage
from pydantic import EmailStr, parse_obj_as, parse_raw_as
from simcore_service_payments.db.auto_recharge_repo import AutoRechargeRepo
from simcore_service_payments.db.payments_methods_repo import PaymentsMethodsRepo
from simcore_service_payments.db.payments_transactions_repo import (
    PaymentsTransactionsRepo,
)

from ..core.settings import ApplicationSettings
from .auto_recharge import get_wallet_auto_recharge
from .payments import pay_with_payment_method
from .payments_gateway import PaymentsGatewayApi
from .rabbitmq import get_rabbitmq_rpc_client

_logger = logging.getLogger(__name__)


async def process_message(app: FastAPI, data: bytes) -> bool:
    rabbit_message = parse_raw_as(WalletCreditsMessage, data)
    _logger.debug("Process msg: %s", rabbit_message)

    settings: ApplicationSettings = app.state.settings

    # 1. Check if wallet credits are bellow the threshold
    if rabbit_message.credits > settings.PAYMENTS_AUTORECHARGE_MIN_BALANCE_IN_CREDITS:
        return True  # --> We do not auto recharge

    # 2. Check if auto-recharge functionality is enabled for wallet_id
    _auto_recharge_repo: AutoRechargeRepo = AutoRechargeRepo(db_engine=app.state.engine)
    wallet_auto_recharge: GetWalletAutoRecharge | None = await get_wallet_auto_recharge(
        settings, _auto_recharge_repo, wallet_id=rabbit_message.wallet_id
    )
    if (
        wallet_auto_recharge is None
        or wallet_auto_recharge.enabled is False
        or wallet_auto_recharge.payment_method_id is None
    ):
        return True  # --> We do not auto recharge

    # 3. Get Payment method
    _payments_repo = PaymentsMethodsRepo(db_engine=app.state.engine)
    payment_method_db = await _payments_repo.get_successful_payment_method_by_id(
        payment_method_id=wallet_auto_recharge.payment_method_id
    )

    # 4. Check whether number of US dollar top-ups is still in the limit
    _payments_transactions_repo = PaymentsTransactionsRepo(db_engine=app.state.engine)
    cumulative_current_month_spending = (
        await _payments_transactions_repo.sum_current_month_dollars(
            wallet_id=rabbit_message.wallet_id
        )
    )
    if (
        wallet_auto_recharge.monthly_limit_in_usd
        is not None  # User had setup monthly limit
        and cumulative_current_month_spending
        + wallet_auto_recharge.top_up_amount_in_usd
        > wallet_auto_recharge.monthly_limit_in_usd
    ):
        _logger.warning(
            "Current month spending would go over the limit %s for payment method %s",
            wallet_auto_recharge.monthly_limit_in_usd,
            wallet_auto_recharge.payment_method_id,
        )
        return True  # --> We do not auto recharge

    # 5. Protective measure: check whether there was not already top up made in the last 5 minutes
    _last_wallet_transaction = (
        await _payments_transactions_repo.get_last_payment_transaction_for_wallet(
            wallet_id=rabbit_message.wallet_id
        )
    )
    _current_timestamp = datetime.now(tz=timezone.utc)
    _current_timestamp_minus_5_minutes = _current_timestamp - timedelta(minutes=5)
    if (
        _last_wallet_transaction
        and _last_wallet_transaction.initiated_at > _current_timestamp_minus_5_minutes
    ):
        _logger.warning(
            "There was already made top up in last 5 minutes, therefore we will pass"
        )
        return True  # --> We do not auto recharge

    # 6. Pay with payment method
    ## 6.1 Ask webserver to compute credits with current dollar/credit ratio
    rabbitmq_rpc_client = get_rabbitmq_rpc_client(app)
    result = await rabbitmq_rpc_client.request(
        WEBSERVER_RPC_NAMESPACE,
        parse_obj_as(RPCMethodName, "get_credit_amount"),
        dollar_amount=wallet_auto_recharge.top_up_amount_in_usd,
        product_name=rabbit_message.product_name,
    )
    credit_result = parse_obj_as(CreditResultGet, result)

    ## 6.2 Make payment
    _payments_gateway = PaymentsGatewayApi.get_from_app_state(app)
    await pay_with_payment_method(
        gateway=_payments_gateway,
        repo_transactions=_payments_transactions_repo,
        repo_methods=_payments_repo,
        payment_method_id=wallet_auto_recharge.payment_method_id,
        amount_dollars=wallet_auto_recharge.top_up_amount_in_usd,
        target_credits=credit_result.credit_amount,
        product_name=rabbit_message.product_name,
        wallet_id=rabbit_message.wallet_id,
        wallet_name=f"id={rabbit_message.wallet_id}",
        user_id=payment_method_db.user_id,
        user_name=f"id={payment_method_db.user_id}",
        user_email=EmailStr(f"placeholder_{payment_method_db.user_id}@example.itis"),
        comment="Payment generated by auto recharge",
    )
    return True
