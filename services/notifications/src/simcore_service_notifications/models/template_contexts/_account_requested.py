"""Context model for the 'account_requested' email template."""

from typing import Any

from models_library.notifications import Channel

from ..template import BaseTemplateContext, register_template_context


@register_template_context(channel=Channel.email, template_name="account_requested")
class AccountRequestedTemplateContext(BaseTemplateContext):
    host: str
    product_info: dict[str, Any]
    request_form: dict[str, Any]
    ipinfo: dict[str, Any]
