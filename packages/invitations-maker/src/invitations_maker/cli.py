from typing import Optional

import typer
from cryptography.fernet import Fernet
from pydantic import EmailStr, parse_obj_as

from .invitations import InvitationData, create_invitation_link
from .settings import ApplicationSettings

main = typer.Typer()


@main.command()
def start():
    """Starts invitation links http server"""
    settings = ApplicationSettings()
    print("Starting server")


@main.command()
def generate_key():
    """Generates secret key

    Example:
        export INVITATIONS_MAKER_SECRET_KEY=$(invitations-maker generate-key)
    """
    print(Fernet.generate_key().decode())


@main.command()
def invite(
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


if __name__ == "__main__":
    main()
