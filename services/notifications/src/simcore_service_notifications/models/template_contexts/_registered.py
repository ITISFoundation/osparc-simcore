"""Context model for the 'registered' email template."""

from models_library.notifications import Channel
from pydantic import BaseModel, HttpUrl

from ..template import BaseTemplateContext, register_template_context


class User(BaseModel):
    first_name: str | None = None
    user_name: str


@register_template_context(channel=Channel.email, template_name="registered")
class RegisteredTemplateContext(BaseTemplateContext):
    user: User
    host: str
    link: HttpUrl
