from typing import Optional

import rich
import typer
from cryptography.fernet import Fernet
from pydantic import EmailStr, parse_obj_as

from . import web
from ._meta import __version__
from .invitations import InvitationData, create_invitation_link
from .settings import ApplicationSettings

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
):
    """Starts server with http API"""
    assert ctx  # nosec
    web.start(log_level="info")


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
def invite(
    ctx: typer.Context,
    email: Optional[str] = typer.Option(
        None,
        callback=lambda v: parse_obj_as(EmailStr, v),
        help="Custom invitation for a given guest",
    ),
    trial_account_days: Optional[int] = typer.Option(
        None,
        help=InvitationData.__fields__["trial_account_days"].field_info.description,
    ),
    issuer: Optional[str] = typer.Option(
        None, help=InvitationData.__fields__["issuer"].field_info.description
    ),
    osparc_url: Optional[str] = typer.Option(
        None,
        help=ApplicationSettings.__fields__[
            "INVITATIONS_MAKER_OSPARC_URL"
        ].field_info.description,
    ),
):
    """Generates invitation links"""
    assert ctx  # nosec
    kwargs = {}

    if osparc_url is not None:
        kwargs["INVITATIONS_MAKER_OSPARC_URL"] = osparc_url

    settings = ApplicationSettings(**kwargs)

    invitation_data = InvitationData(
        issuer=issuer, guest=email, trial_account_days=trial_account_days
    )

    invitation_link = create_invitation_link(
        invitation_data=invitation_data,
        secret_key=settings.INVITATIONS_MAKER_SECRET_KEY.get_secret_value(),
        base_url=settings.INVITATIONS_MAKER_OSPARC_URL,
    )
    print(invitation_link)
