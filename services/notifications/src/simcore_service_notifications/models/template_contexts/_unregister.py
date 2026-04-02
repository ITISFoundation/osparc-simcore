"""Context model for the 'unregister' email template."""

from models_library.notifications import Channel
from pydantic import BaseModel, PositiveInt

from ..template import BaseTemplateContext, register_template_context


class User(BaseModel):
    first_name: str | None = None
    user_name: str


@register_template_context(channel=Channel.email, template_name="unregister")
class UnregisterTemplateContext(BaseTemplateContext):
    user: User
    host: str
    retention_days: PositiveInt
