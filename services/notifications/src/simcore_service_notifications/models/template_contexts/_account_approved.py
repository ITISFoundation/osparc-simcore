"""Context model for the 'account_approved' email template."""

from pydantic import BaseModel, HttpUrl

from ..template import BaseTemplateContext


class User(BaseModel):
    first_name: str | None = None


class AccountApprovedTemplateContext(BaseTemplateContext):
    user: User
    link: HttpUrl

    # extra fields provided by frontend
    trial_account_days: int | None = None
    extra_credits_in_usd: int | None = None
