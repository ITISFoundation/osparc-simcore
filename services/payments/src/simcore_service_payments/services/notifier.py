import asyncio
import contextlib
import logging

from fastapi import FastAPI
from models_library.api_schemas_webserver.wallets import (
    PaymentMethodTransaction,
    PaymentTransaction,
)
from models_library.users import UserID
from servicelib.fastapi.app_state import SingletonInAppStateMixin

from ..core.settings import ApplicationSettings
from ..db.payment_users_repo import PaymentsUsersRepo
from .notifier_abc import NotificationProvider
from .notifier_email import EmailProvider
from .notifier_ws import WebSocketProvider
from .postgres import get_engine

_logger = logging.getLogger(__name__)


class NotifierService(SingletonInAppStateMixin):
    app_state_name: str = "notifier"

    def __init__(self, *providers):
        self.providers: list[NotificationProvider] = list(providers)

    async def notify_payment_completed(
        self,
        user_id: UserID,
        payment: PaymentTransaction,
    ):
        if payment.completed_at is None:
            msg = "Cannot notify unAcked payment"
            raise ValueError(msg)

        await asyncio.gather(
            *(
                provider.notify_payment_completed(user_id=user_id, payment=payment)
                for provider in self.providers
            )
        )

    async def notify_payment_method_acked(
        self,
        user_id: UserID,
        payment_method: PaymentMethodTransaction,
    ):
        if payment_method.state == "PENDING":
            msg = "Cannot notify unAcked payment-method"
            raise ValueError(msg)

        await asyncio.gather(
            *(
                provider.notify_payment_method_acked(
                    user_id=user_id, payment_method=payment_method
                )
                for provider in self.providers
            )
        )


def setup_notifier(app: FastAPI):
    app_settings: ApplicationSettings = app.state.settings

    async def _on_startup() -> None:
        assert app.state.external_socketio  # nosec

        providers: list[NotificationProvider] = [
            WebSocketProvider(
                sio_manager=app.state.external_socketio,
                users_repo=PaymentsUsersRepo(get_engine(app)),
            ),
        ]

        if email_settings := app_settings.PAYMENTS_EMAIL:
            providers.append(
                EmailProvider(
                    email_settings, users_repo=PaymentsUsersRepo(get_engine(app))
                )
            )

        notifier = NotifierService(*providers)
        notifier.set_to_app_state(app)
        assert NotifierService.get_from_app_state(app) == notifier  # nosec

    async def _on_shutdown() -> None:
        with contextlib.suppress(AttributeError):
            NotifierService.pop_from_app_state(app)

    app.add_event_handler("startup", _on_startup)
    app.add_event_handler("shutdown", _on_shutdown)
