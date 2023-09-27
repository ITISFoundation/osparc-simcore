import getpass
import logging

import rich
import typer
from cryptography.fernet import Fernet
from models_library.emails import LowerCaseEmailStr
from pydantic import HttpUrl, SecretStr, ValidationError, parse_obj_as
from rich.console import Console
from servicelib.utils_secrets import generate_password
from settings_library.utils_cli import create_settings_command

from . import web_server
from ._meta import PROJECT_NAME, __version__
from .core.settings import ApplicationSettings, MinimalApplicationSettings
from .invitations import (
    InvalidInvitationCodeError,
    InvitationContent,
    InvitationInputs,
    create_invitation_link,
    extract_invitation_code_from,
    extract_invitation_content,
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
    version: bool
    | None = (
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
        export INVITATIONS_SECRET_KEY=$(invitations-maker generate-key)
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

    username = getpass.getuser()
    password: str = (
        getpass.getpass(prompt="Password [Press Enter to auto-generate]: ")
        if not auto_password
        else None
    ) or generate_password(length=32)

    settings = ApplicationSettings.create_from_envs(
        INVITATIONS_OSPARC_URL="http://127.0.0.1:8000",  # NOSONAR
        INVITATIONS_SECRET_KEY=Fernet.generate_key().decode(),
        INVITATIONS_USERNAME=username,
        INVITATIONS_PASSWORD=password,
    )

    for name, value in settings.dict().items():
        if name.startswith("INVITATIONS_"):
            value = (
                f"{value.get_secret_value()}" if isinstance(value, SecretStr) else value
            )
            print(f"{name}={'null' if value is None else value}")


@app.command()
def invite(
    ctx: typer.Context,
    email: str = typer.Argument(
        ...,
        callback=lambda v: parse_obj_as(LowerCaseEmailStr, v),
        help="Custom invitation for a given guest",
    ),
    issuer: str = typer.Option(
        ..., help=InvitationInputs.__fields__["issuer"].field_info.description
    ),
    trial_account_days: int
    | None = typer.Option(
        None,
        help=InvitationInputs.__fields__["trial_account_days"].field_info.description,
    ),
):
    """Creates an invitation link for user with 'email' and issued by 'issuer'"""
    assert ctx  # nosec
    settings = MinimalApplicationSettings.create_from_envs()

    invitation_data = InvitationInputs(
        issuer=issuer,
        guest=email,
        trial_account_days=trial_account_days,
    )

    invitation_link = create_invitation_link(
        invitation_data=invitation_data,
        secret_key=settings.INVITATIONS_SECRET_KEY.get_secret_value().encode(),
        base_url=settings.INVITATIONS_OSPARC_URL,
    )
    print(invitation_link)


@app.command()
def extract(ctx: typer.Context, invitation_url: str):
    """Validates code and extracts invitation's content"""

    assert ctx  # nosec
    settings = MinimalApplicationSettings.create_from_envs()

    try:
        invitation: InvitationContent = extract_invitation_content(
            invitation_code=extract_invitation_code_from(
                parse_obj_as(HttpUrl, invitation_url)
            ),
            secret_key=settings.INVITATIONS_SECRET_KEY.get_secret_value().encode(),
        )

        rich.print(invitation.json(indent=1))
    except (InvalidInvitationCodeError, ValidationError):
        err_console.print("[bold red]Invalid code[/bold red]")


app.command()(create_settings_command(settings_cls=ApplicationSettings, logger=log))


@app.command()
def serve(
    ctx: typer.Context,
    reload: bool = False,
):
    """Starts server with http API"""
    assert ctx  # nosec
    web_server.start(log_level="info", reload=reload)
