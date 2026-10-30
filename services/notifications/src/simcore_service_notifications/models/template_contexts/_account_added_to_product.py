"""Context model for the 'account_added_to_product' email template."""

from models_library.notifications import Channel
from pydantic import BaseModel

from ..template import BaseTemplateContext, register_template_context


class User(BaseModel):
    first_name: str | None = None


@register_template_context(channel=Channel.email, template_name="account_added_to_product")
class AccountAddedToProductTemplateContext(BaseTemplateContext):
    user: User
    # display name of the existing product closest to the one being granted, if any
    existing_product: str | None = None
