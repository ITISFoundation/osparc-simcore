import logging
from email.headerregistry import Address
from typing import Any, NamedTuple

from jinja2 import Environment
from jinja2.exceptions import TemplateNotFound
from models_library.notifications import ProductData, UserData

_logger = logging.getLogger(__name__)


class EmailPartsTuple(NamedTuple):
    subject: str
    text_content: str
    html_content: str | None


def get_user_address(
    user: UserData,
) -> Address:
    return Address(
        display_name=f"{user.first_name} {user.last_name}",
        addr_spec=user.email,
    )


def get_support_address(product: ProductData) -> Address:
    return Address(
        display_name=f"{product.display_name} support",
        addr_spec=product.support_email,
    )


def render_email_parts(
    env: Environment,
    template_name: str,
    *,
    user: UserData,
    product: ProductData,
    **other_data: Any,
) -> EmailPartsTuple:
    data = other_data | {"user": user, "product": product}

    subject = env.get_template(f"email/{template_name}/subject.j2").render(data)

    text_template = env.get_template(f"email/{template_name}/body_text.j2")
    text_content = text_template.render(data)

    try:
        html_template = env.get_template(f"email/{template_name}/body_html.j2")
        html_content = html_template.render(data)
    except TemplateNotFound as err:
        _logger.debug("Event %s has no html template: %s", template_name, err)
        html_content = None

    return EmailPartsTuple(subject=subject, text_content=text_content, html_content=html_content)
