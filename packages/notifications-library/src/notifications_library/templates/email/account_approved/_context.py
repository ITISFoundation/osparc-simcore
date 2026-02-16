"""Context model for the 'account_approved' email template."""

from notifications_library.context import BaseTemplateContext
from pydantic import BaseModel, HttpUrl


class User(BaseModel):
    first_name: str | None = None


class TemplateContext(BaseTemplateContext):
    user: User
    link: HttpUrl
    trial_account_days: int | None = None
    extra_credits_in_usd: int | None = None
