"""Context model for the 'account_rejected' email template."""

from pydantic import BaseModel

from ..template import BaseTemplateContext


class User(BaseModel):
    first_name: str | None = None


class AccountRejectedTemplateContext(BaseTemplateContext):
    user: User
