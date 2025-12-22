from typing import Annotated

from pydantic import BaseModel, Field

from .channels import Channel
from .events import Event


class NotificationRequest(BaseModel):
    event: Annotated[
        Event,
        Field(
            discriminator="type",
            description=(
                "Event object containing the type discriminator and all event-specific fields. "
                "The type field determines which specific event model is used and validated."
            ),
        ),
    ]

    channel: Annotated[
        Channel,
        Field(
            discriminator="type",
            description=(
                "The channel to use for delivering the notification. "
                "This contains both the type of channel (email, sms, push, etc.) "
                "and the addressing information (email address, phone number, device token)."
            ),
        ),
    ]
