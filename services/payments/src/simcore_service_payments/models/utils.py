from models_library.api_schemas_webserver.wallets import PaymentMethodGet

from .db import PaymentsMethodsDB
from .payments_gateway import GetPaymentMethod


def merge_models(got: GetPaymentMethod, acked: PaymentsMethodsDB) -> PaymentMethodGet:
    assert acked.completed_at  # nosec
    assert got.id == acked.payment_method_id  # nosec

    return PaymentMethodGet(
        idr=acked.payment_method_id,
        wallet_id=acked.wallet_id,
        card_holder_name=got.card_holder_name,
        card_number_masked=got.card_number_masked,
        card_type=got.card_type,
        expiration_month=got.expiration_month,
        expiration_year=got.expiration_year,
        created=acked.completed_at,
        auto_recharge=False,  # this will be fileld in the web/server
    )
