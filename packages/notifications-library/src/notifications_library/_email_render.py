import logging
from email.headerregistry import Address
from typing import NamedTuple

from jinja2 import Environment
from jinja2.exceptions import TemplateNotFound

from ._models import ProductData, UserData

_logger = logging.getLogger(__name__)


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
    **other_data,
) -> EmailPartsTuple:
    from_ = Address(
        display_name=f"{product.display_name} support",
        addr_spec=product.support_email,
    )
    to = Address(
        display_name=f"{user.first_name} {user.last_name}",
        addr_spec=user.email,
    )

    data = other_data | {"user": user, "product": product}

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
