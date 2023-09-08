import getpass
import logging

import typer
from pydantic import SecretStr
from servicelib.utils_secrets import generate_password, generate_token_secret_key
from settings_library.utils_cli import create_settings_command, create_version_callback

from ._meta import PROJECT_NAME, __version__
from .core.settings import ApplicationSettings

_logger = logging.getLogger(__name__)

main = typer.Typer(name=PROJECT_NAME)

main.command()(
    create_settings_command(settings_cls=ApplicationSettings, logger=_logger)
)
main.callback()(create_version_callback(__version__))


@main.command()
def generate_dotenv(ctx: typer.Context, *, auto_password: bool = False):
    """Generates an example of environment variables file (or dot-envfile)

    Usage sample:

    $ simcore-service-payments generate-dotenv > .env

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
        PAYMENTS_GATEWAY_URL="http://127.0.0.1:8000",  # NOSONAR
        PAYMENTS_ACCESS_TOKEN_SECRET_KEY=generate_token_secret_key(32),
        PAYMENTS_USERNAME=username,
        PAYMENTS_PASSWORD=password,
    )

    for name, value in settings.dict().items():
        if name.startswith("PAYMENTS_"):
            new_value = (
                f"{value.get_secret_value()}" if isinstance(value, SecretStr) else value
            )
            print(f"{name}={'null' if new_value is None else new_value}")  # noqa: T201
