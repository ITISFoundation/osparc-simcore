import asyncio
import sys
from datetime import UTC, datetime

import typer
from aiohttp import web
from common_library.users_enums import UserRole
from servicelib.aiohttp.application import create_safe_application
from servicelib.utils_secrets import generate_password
from simcore_postgres_database.models.confirmations import ConfirmationAction
from yarl import URL

from ..application_settings import get_application_settings, setup_settings
from ..db.plugin import setup_db
from . import _account_aggregation_service
from ._invitations_service import ConfirmedInvitationData, get_invitation_url
from .errors import UserAlreadyRegisteredError


def invitations(
    base_url: str,
    issuer_email: str,
    trial_days: int | None = None,
    user_id: int = 1,
    num_codes: int = 15,
    code_length: int = 30,
) -> None:
    """Generates a list of invitation links for registration"""

    invitation = ConfirmedInvitationData(issuer=issuer_email, trial_account_days=trial_days)  # type: ignore[call-arg] # guest field is deprecated

    codes: list[str] = [generate_password(code_length) for _ in range(num_codes)]

    typer.secho(
        "{:-^100}".format("invitations.md"),
        fg=typer.colors.BLUE,
    )

    for i, code in enumerate(codes, start=1):
        url = get_invitation_url(
            {"code": code, "action": ConfirmationAction.INVITATION.name},
            origin=URL(base_url),
        )
        typer.secho(f"{i:2d}. {url}")

    #
    # NOTE: An obvious improvement would be to inject the invitations directly from here
    #       into the database but for that I would add an authentication first. Could
    #       use login auth and give access to only ADMINS
    #

    typer.secho(
        "{:-^100}".format("postgres.csv"),
        fg=typer.colors.BLUE,
    )

    utcnow = datetime.now(tz=UTC)
    today: datetime = utcnow.today()
    print("code,user_id,action,data,created_at", file=sys.stdout)  # noqa: T201
    for n, code in enumerate(codes, start=1):
        print(f'{code},{user_id},INVITATION,"{{', file=sys.stdout)  # noqa: T201
        print(  # noqa: T201
            f'""guest"": ""invitation-{today.year:04d}{today.month:02d}{today.day:02d}-{n}"" ,',
            file=sys.stdout,
        )
        print(f'""issuer"" : ""{invitation.issuer}"" ,', file=sys.stdout)  # noqa: T201
        print(  # noqa: T201
            f'""trial_account_days"" : ""{invitation.trial_account_days}""',
            file=sys.stdout,
        )
        print('}}",{}'.format(utcnow.isoformat(sep=" ")), file=sys.stdout)  # noqa: T201

    typer.secho(
        "-" * 100,
        fg=typer.colors.BLUE,
    )


def _build_db_cli_app() -> web.Application:
    """Minimal aiohttp app exposing only the postgres engine.

    The login/groups/products service functions used below reach the database
    exclusively through `get_asyncpg_engine(app)`, which is wired by `setup_db`.
    """
    app = create_safe_application()
    setup_settings(app)
    setup_db(app)
    return app


def _ensure_development_deployment(app: web.Application) -> None:
    """Fail-closed guard: `create-admin` must never run in a production deployment.

    The check relies on `SC_BOOT_MODE`, which is injected by the docker boot stage
    (e.g. `docker-compose.devel.yml` sets it to `debug` for `make up-devel`) and is
    NOT read from the user-editable `.env` file. Any non-development boot mode -- or
    an undefined one -- is rejected.
    """
    boot_mode = get_application_settings(app).SC_BOOT_MODE
    if boot_mode is None or not boot_mode.is_devel_mode():
        typer.secho(
            f"'create-admin' is disabled in this deployment (SC_BOOT_MODE={boot_mode}). "
            "It is a development-only bootstrap tool (e.g. 'make build-devel up-devel').",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)


def create_admin(
    email: str,
    password: str,
    product_name: str,
) -> None:
    """Creates an ACTIVE ADMIN user account.

    Bootstraps the first privileged user in an empty deployment so that
    invitations and account approvals become possible.
    """

    async def _run() -> None:
        app = _build_db_cli_app()
        _ensure_development_deployment(app)
        runner = web.AppRunner(app)
        await runner.setup()  # enters cleanup_ctx -> creates the postgres engine
        try:
            user = await _account_aggregation_service.create_account(
                app,
                email=email,
                password=password,
                role=UserRole.ADMIN,
                product_name=product_name,
            )
            typer.secho(
                f"Created ADMIN account id={user['id']} email={user['email']} in product '{product_name}'",
                fg=typer.colors.GREEN,
            )
        finally:
            await runner.cleanup()

    try:
        asyncio.run(_run())
    except UserAlreadyRegisteredError as err:
        typer.secho(f"{err}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from err
