import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import cast

from fastapi import FastAPI
from models_library.api_schemas_webserver import WEBSERVER_RPC_NAMESPACE
from models_library.api_schemas_webserver.wallets import (
    GetWalletAutoRecharge,
    PaymentMethodID,
)
from models_library.basic_types import NonNegativeDecimal
from models_library.products import CreditResultGet
from models_library.rabbitmq_basic_types import RPCMethodName
from models_library.rabbitmq_messages import WalletCreditsMessage
from models_library.wallets import WalletID
from pydantic import EmailStr, parse_obj_as, parse_raw_as
from simcore_service_payments.db.auto_recharge_repo import AutoRechargeRepo
from simcore_service_payments.db.payments_methods_repo import PaymentsMethodsRepo
from simcore_service_payments.db.payments_transactions_repo import (
    PaymentsTransactionsRepo,
)
from simcore_service_payments.models.db import PaymentsMethodsDB
from simcore_service_payments.services.resource_usage_tracker import (
    ResourceUsageTrackerApi,
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

    # Step 1: Check if wallet credits are above the threshold
    if await _check_wallet_credits_above_threshold(
        settings.PAYMENTS_AUTORECHARGE_MIN_BALANCE_IN_CREDITS, rabbit_message.credits
    ):
        return True  # We do not auto recharge

    # Step 2: Check auto-recharge conditions
    _auto_recharge_repo: AutoRechargeRepo = AutoRechargeRepo(db_engine=app.state.engine)
    wallet_auto_recharge: GetWalletAutoRecharge | None = await get_wallet_auto_recharge(
        settings, _auto_recharge_repo, wallet_id=rabbit_message.wallet_id
    )
    if await _check_autorecharge_conditions_not_met(wallet_auto_recharge):
        return True  # We do not auto recharge
    assert wallet_auto_recharge is not None  # nosec
    assert wallet_auto_recharge.payment_method_id is not None  # nosec

    # Step 3: Get Payment method
    _payments_repo = PaymentsMethodsRepo(db_engine=app.state.engine)
    payment_method_db = await _payments_repo.get_payment_method_by_id(
        payment_method_id=wallet_auto_recharge.payment_method_id
    )

    # Step 4: Check spending limits
    _payments_transactions_repo = PaymentsTransactionsRepo(db_engine=app.state.engine)
    if await _exceeds_monthly_limit(
        _payments_transactions_repo, rabbit_message.wallet_id, wallet_auto_recharge
    ):
        return True  # We do not auto recharge

    # Step 5: Check last top-up time
    if await _recently_topped_up(_payments_transactions_repo, rabbit_message.wallet_id):
        return True  # We do not auto recharge

    # Step 6: Perform auto-recharge
    if settings.PAYMENTS_AUTORECHARGE_ENABLED:
        await _perform_auto_recharge(
            app, rabbit_message, payment_method_db, wallet_auto_recharge
        )
    return True


async def _check_wallet_credits_above_threshold(
    threshold_in_credits: NonNegativeDecimal, _credits: Decimal
) -> bool:
    return bool(_credits > threshold_in_credits)


async def _check_autorecharge_conditions_not_met(
    wallet_auto_recharge: GetWalletAutoRecharge | None,
) -> bool:
    return (
        wallet_auto_recharge is None
        or wallet_auto_recharge.enabled is False
        or wallet_auto_recharge.payment_method_id is None
    )


async def _exceeds_monthly_limit(
    payments_transactions_repo: PaymentsTransactionsRepo,
    wallet_id: WalletID,
    wallet_auto_recharge: GetWalletAutoRecharge,
):
    cumulative_current_month_spending = (
        await payments_transactions_repo.sum_current_month_dollars(wallet_id=wallet_id)
    )
    return (
        wallet_auto_recharge.monthly_limit_in_usd is not None
        and cumulative_current_month_spending
        + wallet_auto_recharge.top_up_amount_in_usd
        > wallet_auto_recharge.monthly_limit_in_usd
    )


async def _recently_topped_up(
    payments_transactions_repo: PaymentsTransactionsRepo, wallet_id: WalletID
):
    last_wallet_transaction = (
        await payments_transactions_repo.get_last_payment_transaction_for_wallet(
            wallet_id=wallet_id
        )
    )

    current_timestamp = datetime.now(tz=timezone.utc)
    current_timestamp_minus_5_minutes = current_timestamp - timedelta(minutes=5)

    return (
        last_wallet_transaction
        and last_wallet_transaction.initiated_at > current_timestamp_minus_5_minutes
    )


async def _perform_auto_recharge(
    app: FastAPI,
    rabbit_message: WalletCreditsMessage,
    payment_method_db: PaymentsMethodsDB,
    wallet_auto_recharge: GetWalletAutoRecharge,
):
    rabbitmq_rpc_client = get_rabbitmq_rpc_client(app)
    result = await rabbitmq_rpc_client.request(
        WEBSERVER_RPC_NAMESPACE,
        parse_obj_as(RPCMethodName, "get_credit_amount"),
        dollar_amount=wallet_auto_recharge.top_up_amount_in_usd,
        product_name=rabbit_message.product_name,
    )
    credit_result = parse_obj_as(CreditResultGet, result)

    payments_gateway = PaymentsGatewayApi.get_from_app_state(app)
    payments_transactions_repo = PaymentsTransactionsRepo(db_engine=app.state.engine)
    rut_api = ResourceUsageTrackerApi.get_from_app_state(app)

    await pay_with_payment_method(
        gateway=payments_gateway,
        rut=rut_api,
        repo_transactions=payments_transactions_repo,
        repo_methods=PaymentsMethodsRepo(db_engine=app.state.engine),
        payment_method_id=cast(PaymentMethodID, wallet_auto_recharge.payment_method_id),
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
