import getpass
import logging
from typing import Optional

import rich
import typer
from cryptography.fernet import Fernet
from pydantic import EmailStr, HttpUrl, SecretStr, ValidationError, parse_obj_as
from rich.console import Console
from servicelib.utils_secrets import generate_password
from settings_library.utils_cli import create_settings_command

from . import web_server
from ._meta import PROJECT_NAME, __version__
from .core.settings import DesktopApplicationSettings, WebApplicationSettings
from .invitations import (
    InvalidInvitationCode,
    InvitationData,
    create_invitation_link,
    extract_invitation_data,
    parse_invitation_code,
)

# SEE setup entrypoint 'simcore_service_invitations.cli:app'
app = typer.Typer(name=PROJECT_NAME)
log = logging.getLogger(__name__)

err_console = Console(stderr=True)


def _version_callback(value: bool):
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
            callback=_version_callback,
            is_eager=True,
        )
    ),
):
    """o2s2parc invitation maker"""
    assert ctx  # nosec
    assert version or not version  # nosec


#
# COMMANDS
#


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
def generate_dotenv(ctx: typer.Context, auto_password: bool = False):
    """Generates an example of environment variables file (or dot-envfile)

    Usage sample:

    $ invitations-maker generate-dotenv > .env

    $ cat .env

    $ set -o allexport; source .env; set +o allexport
    """
    assert ctx  # nosec

    password: str = (
        getpass.getpass(prompt="Password [Press Enter to auto-generate]: ")
        if not auto_password
        else None
    ) or generate_password(length=32)

    settings = WebApplicationSettings(
        INVITATIONS_MAKER_OSPARC_URL="https://osparc.io",
        INVITATIONS_MAKER_SECRET_KEY=Fernet.generate_key().decode(),
        INVITATIONS_USERNAME=getpass.getuser(),
        INVITATIONS_PASSWORD=password,
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
    email: str = typer.Argument(
        ...,
        callback=lambda v: parse_obj_as(EmailStr, v),
        help="Custom invitation for a given guest",
    ),
    issuer: str = typer.Option(
        ..., help=InvitationData.__fields__["issuer"].field_info.description
    ),
    trial_account_days: Optional[int] = typer.Option(
        None,
        help=InvitationData.__fields__["trial_account_days"].field_info.description,
    ),
):
    """Creates an invitation link for user with 'email' and issued by 'issuer'"""
    assert ctx  # nosec
    settings = DesktopApplicationSettings()

    invitation_data = InvitationData(
        issuer=issuer,
        guest=email,  # type: ignore
        trial_account_days=trial_account_days,
    )

    invitation_link = create_invitation_link(
        invitation_data=invitation_data,
        secret_key=settings.INVITATIONS_MAKER_SECRET_KEY.get_secret_value().encode(),
        base_url=settings.INVITATIONS_MAKER_OSPARC_URL,
    )
    print(invitation_link)


@app.command()
def check(ctx: typer.Context, invitation_url: str):
    """Check invitation code and prints invitation"""

    assert ctx  # nosec
    settings = DesktopApplicationSettings()

    try:
        invitation_data = extract_invitation_data(
            invitation_code=parse_invitation_code(
                parse_obj_as(HttpUrl, invitation_url)
            ),
            secret_key=settings.INVITATIONS_MAKER_SECRET_KEY.get_secret_value().encode(),
        )

        rich.print(invitation_data.json(indent=1))
    except (InvalidInvitationCode, ValidationError):
        err_console.print("[bold red]Invalid code[/bold red]")


app.command()(create_settings_command(settings_cls=WebApplicationSettings, logger=log))


@app.command()
def serve(
    ctx: typer.Context,
    reload: bool = False,
):
    """Starts server with http API"""
    assert ctx  # nosec
    web_server.start(log_level="info", reload=reload)
