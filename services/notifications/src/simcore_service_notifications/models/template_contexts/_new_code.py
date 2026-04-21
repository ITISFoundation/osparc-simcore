"""Context model for the 'new_code' email template."""

from models_library.notifications import Channel
from pydantic import BaseModel

from ..template import BaseTemplateContext, register_template_context


class User(BaseModel):
    first_name: str | None = None
    user_name: str


@register_template_context(channel=Channel.email, template_name="new_code")
class NewCodeTemplateContext(BaseTemplateContext):
    user: User
    host: str
    code: str
