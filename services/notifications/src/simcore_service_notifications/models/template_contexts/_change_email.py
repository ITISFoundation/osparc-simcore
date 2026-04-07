"""Context model for the 'change_email' email template."""

from models_library.notifications import Channel
from pydantic import BaseModel, HttpUrl

from ..template import BaseTemplateContext, register_template_context


class User(BaseModel):
    first_name: str | None = None
    user_name: str


@register_template_context(channel=Channel.email, template_name="change_email")
class ChangeEmailTemplateContext(BaseTemplateContext):
    user: User
    link: HttpUrl
