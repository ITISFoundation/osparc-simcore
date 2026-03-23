"""Context model for the 'reset_password' email template."""

from models_library.notifications import Channel
from pydantic import BaseModel, HttpUrl

from ..template import BaseTemplateContext, register_template_context


class User(BaseModel):
    first_name: str | None = None
    user_name: str


@register_template_context(channel=Channel.email, template_name="reset_password")
class ResetPasswordTemplateContext(BaseTemplateContext):
    user: User
    host: str
    success: bool
    link: HttpUrl | None = None
    reason: str | None = None
