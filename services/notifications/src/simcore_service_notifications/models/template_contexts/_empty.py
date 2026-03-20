"""Context model for the 'empty' email template."""

from models_library.notifications import Channel

from ..template import BaseTemplateContext, register_template_context


@register_template_context(Channel.email, "empty")
class EmptyTemplateContext(BaseTemplateContext):
    subject: str | None = None
    body: str | None = None
