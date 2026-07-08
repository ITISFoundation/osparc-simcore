"""Context model for the 'support_reply' email template."""

from datetime import datetime

from models_library.notifications import Channel
from pydantic import BaseModel, HttpUrl

from ..template import BaseTemplateContext, register_template_context


class User(BaseModel):
    first_name: str | None = None
    user_name: str


@register_template_context(channel=Channel.email, template_name="support_reply")
class SupportReplyTemplateContext(BaseTemplateContext):
    user: User
    conversation_name: str | None
    conversation_url: HttpUrl
    message_content: str
    message_created_at: datetime
