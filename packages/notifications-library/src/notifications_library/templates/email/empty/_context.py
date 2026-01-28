"""Context model for the 'empty' email template."""

from notifications_library.context import BaseTemplateContext


class TemplateContext(BaseTemplateContext):
    subject: str | None = None
    body: str | None = None
