from typing import Any

from models_library.notifications.celery import SmsMessage as CelerySmsMessage
from models_library.notifications.rpc import SmsMessage

from ...core.settings import ApplicationSettings
from ...models.product import Product
from ._base import ChannelHandler


class SmsChannelHandler(ChannelHandler[SmsMessage]):
    """Handles sms channel: fans out into per-recipient payloads.

    NOTE: messaging_service_sid/sender are product-settings-driven and are resolved
    by the celery task itself from product_name (see api/celery/_sms.py), same as
    email resolves smtp extra_headers in its task instead of here.
    """

    @staticmethod
    def prepare_messages(
        message: SmsMessage,
        *,
        # both kept for the handler interface; the sms payload needs neither
        # (product settings are resolved by the celery task, see NOTE above)
        product: Product,  # noqa: ARG004  # pylint: disable=unused-argument
        settings: ApplicationSettings,  # noqa: ARG004  # pylint: disable=unused-argument
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
