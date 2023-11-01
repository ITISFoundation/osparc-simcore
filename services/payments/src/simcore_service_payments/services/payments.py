from models_library.api_schemas_webserver.wallets import WalletPaymentInitiated


async def init_one_time_payment() -> WalletPaymentInitiated:
    raise NotImplementedError


async def cancel_one_time_payment() -> None:
    raise NotImplementedError


async def acknowledge_one_time_payment():
    raise NotImplementedError


async def get_user_payments_page():
    raise NotImplementedError
