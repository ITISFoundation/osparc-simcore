import logging
from dataclasses import dataclass
from email.headerregistry import Address
from typing import Any, NamedTuple

from jinja2 import Environment
from jinja2.exceptions import TemplateNotFound
from models_library.products import ProductName

_logger = logging.getLogger(__name__)


@dataclass
class UserData:
    first_name: str
    last_name: str
    email: str


@dataclass
class ProductData:
    product_name: ProductName
    display_name: str
    vendor_display_inline: str
    support_email: str


class EmailPartsTuple(NamedTuple):
    from_: Address
    to: Address
    suject: str
    text_content: str
    html_content: str | None


def render_email_parts(
    env: Environment,
    event_name: str,
    *,
    user: UserData,
    product: ProductData,
    extra: dict[str, Any] | None = None,
) -> EmailPartsTuple:
    from_ = Address(
        display_name=f"{product.display_name} support",
        addr_spec=product.support_email,
    )
    to = Address(
        display_name=f"{user.first_name} {user.last_name}",
        addr_spec=user.email,
    )

    data = (extra or {}) | {"user": user, "product": product}

    # NOTE: assumes template convention!
    subject = env.get_template(f"{event_name}.email.subject.txt").render(data)

    # Body
    text_template = env.get_template(f"{event_name}.email.content.txt")
    text_content = text_template.render(data)

    try:
        html_template = env.get_template(f"{event_name}.email.content.html")
        html_content = html_template.render(data)
    except TemplateNotFound as err:
        _logger.debug("Event %s has no html template: %s", event_name, err)
        html_content = None

    return EmailPartsTuple(from_, to, subject, text_content, html_content)
