"""Context model for the 'account_rejected' email template."""

from notifications_library.context import BaseTemplateContext
from pydantic import BaseModel


class User(BaseModel):
    first_name: str | None = None


class TemplateContext(BaseTemplateContext):
    user: User
