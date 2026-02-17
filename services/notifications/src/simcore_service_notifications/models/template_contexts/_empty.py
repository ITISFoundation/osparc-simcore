"""Context model for the 'empty' email template."""

from models_library.notifications import ChannelType

from ..template import BaseTemplateContext, register_template_context


@register_template_context(ChannelType.email, "empty")
class EmptyTemplateContext(BaseTemplateContext):
    subject: str | None = None
    body: str | None = None
