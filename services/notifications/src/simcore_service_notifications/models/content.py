from models_library.notifications import ChannelType
from pydantic import BaseModel

from ..exceptions.errors import ContentModelNotFoundError


class Content(BaseModel):
    """Base class for all notification content models."""

    @classmethod
    def get_field_names(cls) -> tuple[str, ...]:
        """Get all field names for this content model (used for template parts)."""
        return tuple(cls.model_fields.keys())


class EmailContent(Content):
    """Email notification content model."""

    subject: str
    body_html: str | None = None
    body_text: str | None = None


_CONTENT_MODELS_BY_CHANNEL: dict[ChannelType, type[Content]] = {
    ChannelType.email: EmailContent,
    # add other channel content models here
}


def for_channel(channel: ChannelType) -> type[Content]:
    """Get content model class for a specific channel."""
    if channel not in _CONTENT_MODELS_BY_CHANNEL:
        raise ContentModelNotFoundError(channel=channel)

    return _CONTENT_MODELS_BY_CHANNEL[channel]
