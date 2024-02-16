import logging
from dataclasses import dataclass
from email.headerregistry import Address
from typing import Any

from jinja2 import Environment
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


def render_email_parts(
    env: Environment,
    template_prefix: str,
    *,
    user: UserData,
    product: ProductData,
    extra: dict[str, Any] | None = None,
) -> tuple:
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
    subject = env.get_template(f"{template_prefix}.email.subject.txt").render(data)

    # Body
    text_template = env.get_template(f"{template_prefix}.email.txt")
    text_content = text_template.render(data)

    html_template = env.get_template(f"{template_prefix}.email.html")
    html_content = html_template.render(data)

    return (from_, to, subject, text_content, html_content)
