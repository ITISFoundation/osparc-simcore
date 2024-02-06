# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import base64
import mimetypes
from contextlib import asynccontextmanager
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


@asynccontextmanager
async def email_session(settings: SMTPSettings):
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

        yield smtp


async def test_it(tmp_environment: EnvVarsDict, osparc_simcore_root_dir: Path):

    settings = SMTPSettings.create_from_envs()

    base_template_html = """\
        <html>
        <head></head>
        <body>
            <div id="content">{% block content %}{% endblock %}</div>
        </body>
        </html>
    """

    movies_template_html = """\
        {% extends "base.html" %}
        {% block content %}
            <h1>Movies</h1>
            <p>
            {% for movie in data['movies'] %} {%if movie['title']!="Terminator" %}
            {{ movie['title'] }}
            {% endif %} {% endfor %}
            </p>
        {% endblock %}
    """

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

        maintype, subtype = guess_file_type(logo_path)
        msg.get_payload(1).add_related(
            logo_path.read_bytes(),
            maintype=maintype,
            subtype=subtype,
            cid=logo_cid,
        )

        # Attach files
        for attachment_path in attachments:
            maintype, subtype = guess_file_type(attachment_path)
            msg.add_attachment(
                attachment_path.read_bytes(),
                filename=attachment_path.name,
                maintype=maintype,
                subtype=subtype,
            )
        return msg

    # this is the new way to cmpose emails
    msg = EmailMessage()
    msg["From"] = Address(display_name="osparc support", addr_spec="support@osparc.io")
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
    msg = compose_branded_email(
        msg, text_body, html_body, attachments=[osparc_simcore_root_dir / "ignore.pdf"]
    )

    async with email_session(settings) as smtp:
        await smtp.send_message(msg)

        # render a template
        # common CSS+HTML

        # compose simple email for
