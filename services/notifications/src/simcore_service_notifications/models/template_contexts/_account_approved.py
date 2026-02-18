"""Context model for the 'account_approved' email template."""

from models_library.notifications import ChannelType
from pydantic import BaseModel, HttpUrl

from ..template import BaseTemplateContext, register_template_context


class User(BaseModel):
    first_name: str | None = None


@register_template_context(channel=ChannelType.email, template_name="account_approved")
class AccountApprovedTemplateContext(BaseTemplateContext):
    user: User
    link: HttpUrl

    # extra fields provided by frontend
    trial_account_days: int | None = None
    extra_credits_in_usd: int | None = None
