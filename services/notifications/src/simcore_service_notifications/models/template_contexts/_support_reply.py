"""Context model for the 'support_reply' email template."""

from models_library.notifications import Channel

from ..template import BaseTemplateContext, register_template_context


@register_template_context(channel=Channel.email, template_name="support_reply")
class SupportReplyTemplateContext(BaseTemplateContext):
    host: str
    recipient_name: str
    sender_name: str
    conversation_name: str
    message_content: str
    conversation_url: str
