import getpass
import random
import secrets
import string
from typing import Optional

import rich
import typer
from cryptography.fernet import Fernet
from pydantic import EmailStr, SecretStr, parse_obj_as

from . import web_server
from ._meta import __version__
from .invitations import InvitationData, create_invitation_link
from .settings import DesktopApplicationSettings, WebApplicationSettings

app = typer.Typer()


def version_callback(value: bool):
    if value:
        rich.print(__version__)
        raise typer.Exit()


@app.callback()
def main(
    ctx: typer.Context,
    version: Optional[bool] = (
        typer.Option(
            None,
            "--version",
            callback=version_callback,
            is_eager=True,
        )
    ),
):
    """o2s2parc invitation maker"""
    assert ctx  # nosec
    assert version or not version  # nosec


@app.command()
def start(
    ctx: typer.Context,
    reload: bool = False,
):
    """Starts server with http API"""
    assert ctx  # nosec
    web_server.start(log_level="info", reload=reload)


@app.command()
def generate_key(
    ctx: typer.Context,
):
    """Generates secret key

    Example:
        export INVITATIONS_MAKER_SECRET_KEY=$(invitations-maker generate-key)
    """
    assert ctx  # nosec
    print(Fernet.generate_key().decode())


@app.command()
def generate_dotenv(ctx: typer.Context):
    """Generates an example of environment variables file (or dot-envfile)

    Example of usage:

    $ invitations-maker generate-dotenv > .env
    $ cat .env
    $ set -o allexport; source .env; set +o allexport
    """
    assert ctx  # nosec

    def _generate_password():
        alphabet = string.digits + string.ascii_letters + string.punctuation
        source = random.sample(alphabet, len(alphabet))
        return "".join(secrets.choice(source) for _ in range(32))

    settings = WebApplicationSettings(
        INVITATIONS_MAKER_OSPARC_URL="https://osparc.io",
        INVITATIONS_MAKER_SECRET_KEY=Fernet.generate_key().decode(),
        INVITATIONS_USERNAME=getpass.getuser(),
        INVITATIONS_PASSWORD=getpass.getpass(
            prompt="Password [Press Enter to auto-generate]: "
        )
        or _generate_password(),
    )

    for name, value in settings.dict().items():
        value = (
            f'"{value.get_secret_value()}"'
            if isinstance(value, SecretStr)
            else f"{value}"
        )
        print(f"{name}={value}")


@app.command()
def invite(
    ctx: typer.Context,
    email: str = typer.Option(
        None,
        callback=lambda v: parse_obj_as(EmailStr, v),
        help="Custom invitation for a given guest",
    ),
    trial_account_days: Optional[int] = typer.Option(
        None,
        help=InvitationData.__fields__["trial_account_days"].field_info.description,
    ),
    issuer: str = typer.Option(
        None, help=InvitationData.__fields__["issuer"].field_info.description
    ),
):
    """Generates invitation links"""
    assert ctx  # nosec
    kwargs = {}

    settings = DesktopApplicationSettings(**kwargs)

    invitation_data = InvitationData(
        issuer=issuer, guest=email, trial_account_days=trial_account_days
    )

    invitation_link = create_invitation_link(
        invitation_data=invitation_data,
        secret_key=settings.INVITATIONS_MAKER_SECRET_KEY.get_secret_value(),
        base_url=settings.INVITATIONS_MAKER_OSPARC_URL,
    )
    print(invitation_link)
