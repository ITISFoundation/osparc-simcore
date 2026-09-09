from typing import Any

from models_library.notifications.celery import SmsMessage as CelerySmsMessage
from models_library.notifications.rpc import SmsMessage

from ...core.settings import ApplicationSettings
from ...models.product import Product
from ._base import ChannelHandler


class SmsChannelHandler(ChannelHandler):
    """Handles sms channel: fans out into per-recipient payloads.

    NOTE: messaging_service_sid/sender are product-settings-driven and are resolved
    by the celery task itself from product_name (see api/celery/_sms.py), same as
    email resolves smtp extra_headers in its task instead of here.
    """

    @staticmethod
    def prepare_messages(
        message: SmsMessage,
        *,
        product: Product,  # noqa: ARG004
        settings: ApplicationSettings,  # noqa: ARG004
    ) -> list[dict[str, Any]]:
        return [
            CelerySmsMessage.model_validate(
                {
                    "channel": message.channel,
                    "to": recipient.model_dump(),
                    "body": message.content.body,
                }
            ).model_dump()
            for recipient in message.addressing.to
        ]
