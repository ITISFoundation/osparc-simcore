import logging
import os

import typer
from settings_library.docker_api_proxy import DockerApiProxysettings
from settings_library.rabbit import RabbitSettings
from settings_library.utils_cli import (
    create_settings_command,
    create_version_callback,
    print_as_envfile,
)

from ._meta import PROJECT_NAME, __version__
from .core.settings import ApplicationSettings

_logger = logging.getLogger(__name__)

main = typer.Typer(name=PROJECT_NAME)

main.command()(
    create_settings_command(settings_cls=ApplicationSettings, logger=_logger)
)
main.callback()(create_version_callback(__version__))


@main.command()
def echo_dotenv(ctx: typer.Context, *, minimal: bool = True):
    """Generates and displays a valid environment variables file (also known as dot-envfile)

    Usage:
        $ simcore-service-dynamic-scheduler echo-dotenv > .env
        $ cat .env
        $ set -o allexport; source .env; set +o allexport
    """
    assert ctx  # nosec

    # NOTE: we normally DO NOT USE `os.environ` to capture env vars but this is a special case
    # The idea here is to have a command that can generate a **valid** `.env` file that can be used
    # to initialized the app. For that reason we fill required fields of the `ApplicationSettings` with
    # "fake" but valid values (e.g. generating a password or adding tags as `replace-with-api-key).
    # Nonetheless, if the caller of this CLI has already some **valid** env vars in the environment we want to use them ...
    # and that is why we use `os.environ`.

    settings = ApplicationSettings.create_from_envs(
        DYNAMIC_SCHEDULER_RABBITMQ=os.environ.get(
            "DYNAMIC_SCHEDULER_RABBITMQ",
            RabbitSettings.create_from_envs(
                RABBIT_HOST=os.environ.get("RABBIT_HOST", "replace-with-rabbit-host"),
                RABBIT_SECURE=os.environ.get("RABBIT_SECURE", "0"),
                RABBIT_USER=os.environ.get("RABBIT_USER", "replace-with-rabbit-user"),
                RABBIT_PASSWORD=os.environ.get(
                    "RABBIT_PASSWORD", "replace-with-rabbit-user"
                ),
            ),
        ),
        DYNAMIC_SCHEDULER_UI_STORAGE_SECRET=os.environ.get(
            "DYNAMIC_SCHEDULER_UI_STORAGE_SECRET",
            "replace-with-ui-storage-secret",
        ),
        DYNAMIC_SCHEDULER_DOCKER_API_PROXY=os.environ.get(
            "DYNAMIC_SCHEDULER_DOCKER_API_PROXY",
            DockerApiProxysettings.create_from_envs(
                DOCKER_API_PROXY_HOST=os.environ.get(
                    "DOCKER_API_PROXY_HOST", "replace-with-proxy-host"
                )
            ),
        ),
    )

    print_as_envfile(
        settings,
        compact=False,
        verbose=True,
        show_secrets=True,
        exclude_unset=minimal,
    )
