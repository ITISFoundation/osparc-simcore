import contextlib

from fastapi import FastAPI
from fastapi_mail import ConnectionConfig, FastMail
from pydantic import EmailStr
from servicelib.fastapi.app_state import SingletonInAppStateMixin
from settings_library.email import EmailProtocol, SMTPSettings

from ..core.settings import ApplicationSettings


class EmailNotifier(SingletonInAppStateMixin):
    app_state_name: str = "email_notifier"

    def __init__(
        self, settings: SMTPSettings, support_email: EmailStr, support_display_name: str
    ):

        assert settings.SMTP_USERNAME
        assert settings.SMTP_PASSWORD

        conf = ConnectionConfig(
            MAIL_USERNAME=settings.SMTP_USERNAME,
            MAIL_PASSWORD=settings.SMTP_PASSWORD.get_secret_value(),
            MAIL_PORT=settings.SMTP_PORT,
            MAIL_SERVER=settings.SMTP_HOST,
            MAIL_TLS=settings.SMTP_PROTOCOL == EmailProtocol.TLS,
            MAIL_SSL=settings.SMTP_PROTOCOL == EmailProtocol.STARTTLS,
            MAIL_DEBUG=0,
            MAIL_FROM=support_email,
            MAIL_FROM_NAME=support_display_name,
            TEMPLATE_FOLDER=None,
            SUPPRESS_SEND=0,
            USE_CREDENTIALS=True,
            VALIDATE_CERTS=True,
        )
        self._fm = FastMail(conf)

    async def send_message(self, message):
        await self._fm.send_message(message)


def setup_notifier_email(app: FastAPI):
    app_settings: ApplicationSettings = app.state.settings

    if settings := app_settings.PAYMENTS_EMAIL:

        async def _on_startup() -> None:
            assert app.state.external_socketio  # nosec

            notifier = EmailNotifier(settings)
            notifier.set_to_app_state(app)

            assert EmailNotifier.get_from_app_state(app) == notifier  # nosec

        async def _on_shutdown() -> None:
            with contextlib.suppress(AttributeError):
                EmailNotifier.pop_from_app_state(app)

        app.add_event_handler("startup", _on_startup)
        app.add_event_handler("shutdown", _on_shutdown)
