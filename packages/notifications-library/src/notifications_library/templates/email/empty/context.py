"""Context model for the 'empty' email template."""

from notifications_library.template_context import NotificationsTemplateContext


class Context(NotificationsTemplateContext):
    subject: str | None = None
    body: str | None = None
