import getpass
import logging

import typer
from cryptography.fernet import Fernet
from models_library.emails import LowerCaseEmailStr
from models_library.invitations import InvitationContent, InvitationInputs
from pydantic import EmailStr, HttpUrl, TypeAdapter, ValidationError
from rich.console import Console
from servicelib.utils_secrets import generate_password
from settings_library.utils_cli import (
    create_settings_command,
    create_version_callback,
    print_as_envfile,
)

from . import web_server
from ._meta import PROJECT_NAME, __version__
from .core.settings import ApplicationSettings, MinimalApplicationSettings
from .services.invitations import (
    InvalidInvitationCodeError,
    create_invitation_link_and_content,
    extract_invitation_code_from_query,
    extract_invitation_content,
)

_logger = logging.getLogger(__name__)
_err_console = Console(stderr=True)

# SEE setup entrypoint 'simcore_service_invitations.cli:main'
main = typer.Typer(name=PROJECT_NAME)
main.command()(
    create_settings_command(settings_cls=ApplicationSettings, logger=_logger)
)
main.callback()(create_version_callback(__version__))


#
# COMMANDS
#


@main.command()
def generate_key(
    ctx: typer.Context,
):
    """Generates secret key

    Example:
        export INVITATIONS_SECRET_KEY=$(invitations-maker generate-key)
    """
    assert ctx  # nosec
    print(Fernet.generate_key().decode())  # noqa: T201


@main.command()
def echo_dotenv(
    ctx: typer.Context, *, auto_password: bool = False, minimal: bool = True
):
    """Echos an example of environment variables file (or dot-envfile)

    Usage sample:

    $ invitations-maker echo-dotenv > .env
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
        INVITATIONS_DEFAULT_PRODUCT="s4llite",
        INVITATIONS_SECRET_KEY=Fernet.generate_key().decode(),
        INVITATIONS_USERNAME=username,
        INVITATIONS_PASSWORD=password,
    )

    print_as_envfile(
        settings,
        compact=False,
        verbose=True,
        show_secrets=True,
        exclude_unset=minimal,
    )


@main.command()
def invite(
    ctx: typer.Context,
    email: str = typer.Argument(
        ...,
        callback=lambda v: TypeAdapter(LowerCaseEmailStr).validate_python(v),
        help="Custom invitation for a given guest",
    ),
    issuer: str = typer.Option(
        ..., help=InvitationInputs.model_fields["issuer"].description
    ),
    trial_account_days: int = typer.Option(
        None,
        help=InvitationInputs.model_fields["trial_account_days"].description,
    ),
    product: str = typer.Option(
        None,
        help=InvitationInputs.model_fields["product"].description,
    ),
):
    """Creates an invitation link for user with 'email' and issued by 'issuer'"""
    assert ctx  # nosec
    settings = MinimalApplicationSettings.create_from_envs()

    invitation_data = InvitationInputs(
        issuer=issuer,
        guest=TypeAdapter(EmailStr).validate_python(email),
        trial_account_days=trial_account_days,
        extra_credits_in_usd=None,
        product=product,
    )

    invitation_link, _ = create_invitation_link_and_content(
        invitation_data=invitation_data,
        secret_key=settings.INVITATIONS_SECRET_KEY.get_secret_value().encode(),  # pylint:disable=no-member
        base_url=settings.INVITATIONS_OSPARC_URL,
        default_product=settings.INVITATIONS_DEFAULT_PRODUCT,
    )
    print(invitation_link)  # noqa: T201


@main.command()
def extract(ctx: typer.Context, invitation_url: str):
    """Validates code and extracts invitation's content"""

    assert ctx  # nosec
    settings = MinimalApplicationSettings.create_from_envs()

    try:
        invitation: InvitationContent = extract_invitation_content(
            invitation_code=extract_invitation_code_from_query(
                TypeAdapter(HttpUrl).validate_python(invitation_url)
            ),
            secret_key=settings.INVITATIONS_SECRET_KEY.get_secret_value().encode(),  # pylint:disable=no-member
            default_product=settings.INVITATIONS_DEFAULT_PRODUCT,
        )
        assert invitation.product is not None  # nosec

        print(invitation.model_dump_json(indent=1))  # noqa: T201

    except (InvalidInvitationCodeError, ValidationError):
        _err_console.print("[bold red]Invalid code[/bold red]")


@main.command()
def serve(
    ctx: typer.Context,
    *,
    reload: bool = False,
):
    """Starts server with http API"""
    assert ctx  # nosec
    web_server.start(log_level="info", reload=reload)
