# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import mimetypes
from email.headerregistry import Address
from email.message import EmailMessage
from email.utils import make_msgid
from pathlib import Path

import aiosmtplib
import pytest
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_envs import setenvs_from_envfile
from settings_library.email import EmailProtocol, SMTPSettings


@pytest.fixture
def tmp_environment(
    osparc_simcore_root_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> EnvVarsDict:
    return setenvs_from_envfile(monkeypatch, osparc_simcore_root_dir / ".secrets")


def guess_file_type(file_path: Path) -> tuple[str, str]:
    assert file_path.is_file()
    mimetype, _encoding = mimetypes.guess_type(file_path)
    if mimetype:
        maintype, subtype = mimetype.split("/", maxsplit=1)
    else:
        maintype, subtype = "application", "octet-stream"
    return maintype, subtype


async def test_it(tmp_environment: EnvVarsDict, osparc_simcore_root_dir: Path):

    settings = SMTPSettings.create_from_envs()

    async with aiosmtplib.SMTP(
        hostname=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
        # FROM https://aiosmtplib.readthedocs.io/en/stable/usage.html#starttls-connections
        # By default, if the server advertises STARTTLS support, aiosmtplib will upgrade the connection automatically.
        # Setting use_tls=True for STARTTLS servers will typically result in a connection error
        # To opt out of STARTTLS on connect, pass start_tls=False.
        # NOTE: for that reason TLS and STARTLS are mutally exclusive
        use_tls=settings.SMTP_PROTOCOL == EmailProtocol.TLS,
        start_tls=settings.SMTP_PROTOCOL == EmailProtocol.STARTTLS,
    ) as smtp:
        if settings.has_credentials:
            assert settings.SMTP_USERNAME
            assert settings.SMTP_PASSWORD
            await smtp.login(
                settings.SMTP_USERNAME,
                settings.SMTP_PASSWORD.get_secret_value(),
            )

        def compose_email(msg: EmailMessage, text_body, html_body) -> EmailMessage:
            # Text version
            msg.set_content(
                f"""\
                {text_body}

                Done with love at Z43
            """
            )

            # HTML version
            logo_cid = make_msgid()
            msg.add_alternative(
                f"""\
            <html>
            <head></head>
            <body>
                {html_body}
                Done with love at <img src="cid:{logo_cid[1:-1]}" width=30/>
            </body>
            </html>
            """,
                subtype="html",
            )

            assert msg.is_multipart()

            logo_path = (
                osparc_simcore_root_dir
                / "services/static-webserver/client/source/resource/osparc/z43-logo.png"
            )
            maintype, subtype = guess_file_type(logo_path)
            msg.get_payload(1).add_related(
                logo_path.read_bytes(),
                maintype=maintype,
                subtype=subtype,
                cid=logo_cid,
            )

            # Attach file
            pdf_path = osparc_simcore_root_dir / "ignore.pdf"
            maintype, subtype = guess_file_type(pdf_path)
            msg.add_attachment(
                pdf_path.read_bytes(),
                filename=pdf_path.name,
                maintype=maintype,
                subtype=subtype,
            )
            return msg

        msg = EmailMessage()
        msg["From"] = Address(
            display_name="osparc support", addr_spec="support@osparc.io"
        )
        msg["To"] = Address(
            display_name="Pedro Crespo-Valero", addr_spec="crespo@speag.com"
        )
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
        msg = compose_email(msg, text_body, html_body)

        await smtp.send_message(msg)

        # render a template
        # common CSS+HTML
