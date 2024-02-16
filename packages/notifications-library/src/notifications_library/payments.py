import contextlib
import logging
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass
from email.headerregistry import Address
from email.message import EmailMessage
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from models_library.api_schemas_webserver.wallets import (
    PaymentMethodTransaction,
    PaymentTransaction,
)
from models_library.users import UserID
from servicelib.file_utils import remove_directory

from ._db import TemplatesRepo
from ._render import ProductData, UserData

_logger = logging.getLogger(__name__)


_PRODUCT_NOTIFICATIONS_TEMPLATES = {
    "base.html",
    "notify_payments.email.html",
    "notify_payments.email.txt",
    "notify_payments.email.subject.txt",
}


@dataclass
class PaymentData:
    price_dollars: str
    osparc_credits: str
    invoice_url: str


async def _create_user_email(
    env: Environment,
    user: UserData,
    payment: PaymentData,
    product: ProductData,
) -> EmailMessage:
    # data to interpolate template
    data = {
        "user": user,
        "product": product,
        "payment": payment,
    }

    msg = EmailMessage()

    msg["From"] = Address(
        display_name=f"{product.display_name} support",
        addr_spec=product.support_email,
    )
    msg["To"] = Address(
        display_name=f"{user.first_name} {user.last_name}",
        addr_spec=user.email,
    )
    msg["Subject"] = env.get_template("notify_payments.email.subject.txt").render(data)

    # Body
    text_template = env.get_template("notify_payments.email.txt")
    msg.set_content(text_template.render(data))

    html_template = env.get_template("notify_payments.email.html")
    msg.add_alternative(html_template.render(data), subtype="html")
    return msg


@contextlib.asynccontextmanager
async def _jinja_environment_lifespan(repo: TemplatesRepo):
    expected = _PRODUCT_NOTIFICATIONS_TEMPLATES
    templates = await repo.get_email_templates(names=expected)

    if not templates:
        raise TemplatesNotFoundError(templates=expected)

    temp_dir = Path(tempfile.mkdtemp(suffix="templates_{__name__}"))
    assert temp_dir.is_dir()  # nosec

    for name, content in templates.items():
        (temp_dir / name).write_text(content)

    env = Environment(
        loader=FileSystemLoader(searchpath=temp_dir),
        autoescape=select_autoescape(["html", "xml"]),
    )

    yield env

    await remove_directory(temp_dir, ignore_errors=True)


class PaymentsNotifier(ABC):
    @abstractmethod
    async def notify_payment_completed(
        self,
        user_id: UserID,
        payment: PaymentTransaction,
    ):
        ...

    @abstractmethod
    async def notify_payment_method_acked(
        self,
        user_id: UserID,
        payment_method: PaymentMethodTransaction,
    ):
        ...
