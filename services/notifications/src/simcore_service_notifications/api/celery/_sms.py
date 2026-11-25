# pylint: disable=unused-argument

import logging
from typing import Final

from celery import (  # type: ignore[import-untyped]
    Task,
)
from common_library.masking import mask_phone_number
from models_library.celery import TaskKey
from models_library.notifications.celery import SmsMessage
from models_library.products import ProductName
from servicelib.logging_utils import log_context
from twilio.base.exceptions import (  # type: ignore[import-untyped]
    TwilioException,
    TwilioRestException,
)

from ...clients.twilio import send_sms
from ...core.settings import ApplicationSettings, NotificationsTwilioSettings
from ...exceptions.errors import (
    NotificationsSmsDeliveryError,
    NotificationsSmsDeliveryPermanentError,
)

_logger = logging.getLogger(__name__)

# 4xx the provider may recover from, so they stay retryable
_TRANSIENT_4XX: Final[frozenset[int]] = frozenset({408, 429})
_HTTP_CLIENT_ERROR_MIN: Final[int] = 400
_HTTP_SERVER_ERROR_MIN: Final[int] = 500


def _is_permanent_rejection(exc: TwilioRestException) -> bool:
    status = exc.status
    return (
        isinstance(status, int)
        and _HTTP_CLIENT_ERROR_MIN <= status < _HTTP_SERVER_ERROR_MIN
        and status not in _TRANSIENT_4XX
    )


async def send_sms_message_task(
    task: Task,
    task_key: TaskKey,
    product_name: ProductName,
    message: SmsMessage,
) -> None:
    assert task  # nosec
    assert task_key  # nosec

    masked_phone_number = mask_phone_number(message.to.phone_number)

    with log_context(_logger, logging.INFO, "Send sms to %s", masked_phone_number):
        app_settings = ApplicationSettings.create_from_envs()
        assert app_settings.NOTIFICATIONS_TWILIO_SETTINGS is not None  # nosec
        twilio_settings: NotificationsTwilioSettings = app_settings.NOTIFICATIONS_TWILIO_SETTINGS

        product_twilio_settings = twilio_settings.get_product_twilio_settings(product_name)
        account_settings = twilio_settings.get_twilio_account_settings(product_name)

        # NOTE: alphanumeric sender IDs are not supported in every country
        sender = (
            product_twilio_settings.alphanumeric_sender_id
            if account_settings.is_alphanumeric_supported(message.to.phone_number)
            else None
        )

        try:
            await send_sms(
                account_settings,
                messaging_service_sid=product_twilio_settings.messaging_service_sid,
                to=message.to.phone_number,
                body=message.body,
                sender=sender,
            )
        except TwilioRestException as exc:
            # NOTE: never surface the raw provider error, phone number or body in the exception message
            if _is_permanent_rejection(exc):
                raise NotificationsSmsDeliveryPermanentError(masked_phone_number=masked_phone_number) from exc
            raise NotificationsSmsDeliveryError(masked_phone_number=masked_phone_number) from exc
        except TwilioException as exc:
            raise NotificationsSmsDeliveryError(masked_phone_number=masked_phone_number) from exc
