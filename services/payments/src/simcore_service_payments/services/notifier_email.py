from models_library.api_schemas_webserver.wallets import (
    PaymentMethodTransaction,
    PaymentTransaction,
)
from models_library.users import UserID
from settings_library.email import SMTPSettings

from ..db.payment_users_repo import PaymentsUsersRepo
from .notifier_abc import NotificationProvider


class EmailService:
    # renders and sends emails
    ...


class EmailProvider(NotificationProvider):
    # interfaces with the notification system
    def __init__(self, settings: SMTPSettings, users_repo: PaymentsUsersRepo):
        ...

    async def notify_payment_completed(
        self,
        user_id: UserID,
        payment: PaymentTransaction,
    ):

        raise NotImplementedError

    async def notify_payment_method_acked(
        self,
        user_id: UserID,
        payment_method: PaymentMethodTransaction,
    ):
        raise NotImplementedError
