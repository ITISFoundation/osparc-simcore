import logging
from email.headerregistry import Address
from typing import Any

from attr import dataclass
from jinja2 import Environment
from models_library.products import ProductName

_logger = logging.getLogger(__name__)


@dataclass
class _UserData:
    first_name: str
    last_name: str
    email: str


@dataclass
class _ProductData:
    product_name: ProductName
    display_name: str
    vendor_display_inline: str
    support_email: str


async def render_email_parts(
    env: Environment,
    template_prefix: str,
    user: _UserData,
    product: _ProductData,
    data: dict[str, Any],
) -> tuple:
    from_ = Address(
        display_name=f"{product.display_name} support",
        addr_spec=product.support_email,
    )
    to = Address(
        display_name=f"{user.first_name} {user.last_name}",
        addr_spec=user.email,
    )

    # NOTE: assumes template convention!
    subject = env.get_template(f"{template_prefix}.email.subject.txt").render(data)

    # Body
    text_template = env.get_template(f"{template_prefix}.email.txt")
    text_content = text_template.render(data)

    html_template = env.get_template(f"{template_prefix}.email.html")
    html_content = html_template.render(data)

    return (from_, to, subject, text_content, html_content)
