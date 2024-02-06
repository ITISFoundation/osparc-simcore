# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import base64
from decimal import Decimal
from email.headerregistry import Address
from email.message import EmailMessage
from email.utils import make_msgid
from pathlib import Path

import arrow
import pytest
from faker import Faker
from jinja2 import DictLoader, Environment, select_autoescape
from models_library.api_schemas_webserver.wallets import PaymentTransaction
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_envs import setenvs_from_envfile
from settings_library.email import SMTPSettings
from simcore_service_payments.services.notifier_email import (
    _PRODUCT_NOTIFICATIONS_TEMPLATES,
    _add_attachments,
    _create_email_session,
    _create_user_email,
    _guess_file_type,
    _ProductData,
    _UserData,
)


def run_trials(osparc_simcore_root_dir: Path):
    def compose_branded_email(
        msg: EmailMessage, text_body, html_body, attachments: list[Path]
    ) -> EmailMessage:
        # Text version
        msg.set_content(
            f"""\
            {text_body}

            Done with love at Z43
        """
        )

        # HTML version
        logo_path = (
            osparc_simcore_root_dir
            / "services/static-webserver/client/source/resource/osparc/z43-logo.png"
        )

        encoded = base64.b64encode(logo_path.read_bytes()).decode()
        img_src_as_base64 = f'"data:image/jpg;base64,{encoded}">'
        assert img_src_as_base64

        # Adding an image as CID attachments (which get embedded with a MIME object)
        logo_cid = make_msgid()
        img_src_as_cid_atttachment = f'"cid:{logo_cid[1:-1]}"'

        img_src = img_src_as_cid_atttachment
        msg.add_alternative(
            f"""\
        <html>
        <head></head>
        <body>
            {html_body}
            Done with love at <img src={img_src} width=30/>
        </body>
        </html>
        """,
            subtype="html",
        )

        assert msg.is_multipart()

        maintype, subtype = _guess_file_type(logo_path)
        msg.get_payload(1).add_related(
            logo_path.read_bytes(),
            maintype=maintype,
            subtype=subtype,
            cid=logo_cid,
        )

        # Attach files
        _add_attachments(msg, attachments)
        return msg

    # this is the new way to cmpose emails
    msg = EmailMessage()
    msg["From"] = Address(display_name="osparc support", addr_spec="support@osparc.io")
    msg["Subject"] = "Payment invoice"
    text_body = """\
    Hi there,

    This is your invoice.
    """

    html_body = """\
    <p>Hi there!</p>
    <p>This is your
        <a href="http://www.yummly.com/recipe/Roasted-Asparagus-Epicurious-203718">
            invoice
        </a>.
    </p>
    """
    msg = compose_branded_email(
        msg, text_body, html_body, attachments=[osparc_simcore_root_dir / "ignore.pdf"]
    )


@pytest.fixture
def tmp_environment(
    osparc_simcore_root_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> EnvVarsDict:
    return setenvs_from_envfile(monkeypatch, osparc_simcore_root_dir / ".secrets")


@pytest.fixture
def user(
    faker: Faker,
):
    return _UserData(
        first_name="Pedrolito", last_name="Crespo", email="crespo@itis.swiss"
    )


@pytest.mark.skip(reason="DEV ONLY")
async def test_it(
    tmp_environment: EnvVarsDict,
    osparc_simcore_root_dir: Path,
    tmp_path: Path,
    faker: Faker,
    user: _UserData,
):
    settings = SMTPSettings.create_from_envs()
    env = Environment(
        loader=DictLoader(_PRODUCT_NOTIFICATIONS_TEMPLATES),
        autoescape=select_autoescape(["html", "xml"]),
    )

    product = _ProductData(
        product_name="osparc",
        display_name="o²S²PARC",
        vendor_display_inline="IT'IS Foundation. Zeughausstrasse 43, 8004 Zurich, Switzerland ",
        support_email="support@osparc.io",
    )
    payment = PaymentTransaction(
        payment_id="pt_123234",
        price_dollars=Decimal(1),
        wallet_id=12,
        osparc_credits=Decimal(10),
        comment="fake",
        created_at=arrow.now().datetime,
        completed_at=arrow.now().datetime,
        completedStatus="SUCCESS",
        state_message="ok",
        invoice_url=faker.image_url(),
    )

    msg = await _create_user_email(env, user, payment, product)

    attachment = tmp_path / "attachment.txt"
    attachment.write_text(faker.text())
    _add_attachments(msg, [attachment])

    async with _create_email_session(settings) as smtp:
        await smtp.send_message(msg)
