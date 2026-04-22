"""Context model for the 'paid' email template."""

from models_library.notifications import Channel
from pydantic import BaseModel

from ..template import BaseTemplateContext, register_template_context


class User(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    user_name: str | None = None
    email: str | None = None


class Payment(BaseModel):
    price_dollars: str
    osparc_credits: str
    invoice_url: str


@register_template_context(channel=Channel.email, template_name="paid")
class PaidTemplateContext(BaseTemplateContext):
    user: User
    payment: Payment
