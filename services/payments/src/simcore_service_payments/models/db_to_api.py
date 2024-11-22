from typing import Any

from models_library.api_schemas_webserver.wallets import (
    PaymentMethodTransaction,
    PaymentTransaction,
)

from .db import PaymentsMethodsDB, PaymentsTransactionsDB


def to_payments_api_model(transaction: PaymentsTransactionsDB) -> PaymentTransaction:
    data: dict[str, Any] = {
        "payment_id": transaction.payment_id,
        "price_dollars": transaction.price_dollars,
        "osparc_credits": transaction.osparc_credits,
        "wallet_id": transaction.wallet_id,
        "created_at": transaction.initiated_at,
        "state": f"{transaction.state}",
        "completed_at": transaction.completed_at,
    }

    if transaction.comment:
        data["comment"] = transaction.comment

    if transaction.state_message:
        data["state_message"] = transaction.state_message

    if transaction.invoice_url:
        data["invoice_url"] = transaction.invoice_url

    return PaymentTransaction(**data)


def to_payment_method_api_model(
    payment_method: PaymentsMethodsDB,
) -> PaymentMethodTransaction:
    return PaymentMethodTransaction(
        wallet_id=payment_method.wallet_id,
        payment_method_id=payment_method.payment_method_id,
        state=payment_method.state.value,
    )
