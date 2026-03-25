"""Context model for the 'account_rejected' email template."""

from models_library.notifications import Channel
from pydantic import BaseModel

from ..template import BaseTemplateContext, register_template_context


class User(BaseModel):
    first_name: str | None = None


@register_template_context(Channel.email, "account_rejected")
class AccountRejectedTemplateContext(BaseTemplateContext):
    user: User
