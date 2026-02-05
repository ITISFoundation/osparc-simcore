"""Context model for the 'account_approved' email template."""

from notifications_library.context import BaseTemplateContext
from pydantic import HttpUrl


class User:
    first_name: str | None = None
    user_name: str


class TemplateContext(BaseTemplateContext):
    user: User
    link: HttpUrl
