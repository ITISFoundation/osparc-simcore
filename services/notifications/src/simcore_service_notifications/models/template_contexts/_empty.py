"""Context model for the 'empty' email template."""

from ..template import BaseTemplateContext


class EmptyTemplateContext(BaseTemplateContext):
    subject: str | None = None
    body: str | None = None
