""" Application's command line .

Why does this file exist, and why not put this in __main__?

  You might be tempted to import things from __main__ later, but that will cause
  problems: the code will get executed twice:

  - When you run `python -msimcore_service_webserver` python will execute
    ``__main__.py`` as a script. That means there won't be any
    ``simcore_service_webserver.__main__`` in ``sys.modules``.
  - When you import __main__ it will get executed again (as a module) because
    there's no ``simcore_service_webserver.__main__`` in ``sys.modules``.

"""

import logging
import os
from typing import Final

import typer
from aiohttp import web
from settings_library.utils_cli import create_settings_command
from typing_extensions import Annotated

from .application_settings import ApplicationSettings
from .login import cli as login_cli

# ptsvd cause issues with ProcessPoolExecutor
# SEE: https://github.com/microsoft/ptvsd/issues/1443
if os.environ.get("SC_BOOT_MODE") == "debug":
    import multiprocessing

    multiprocessing.set_start_method("spawn", True)

_logger = logging.getLogger(__name__)


def _setup_app_from_settings(
    settings: ApplicationSettings,
) -> tuple[web.Application, dict]:
    # NOTE: keeping imports here to reduce CLI load time
    from .application import create_application
    from .application_settings_utils import convert_to_app_config
    from .log import setup_logging

    # NOTE: By having an equivalent config allows us
    # to keep some of the code from the previous
    # design whose starting point was a validated
    # config. E.g. many test fixtures were based on
    # given configs and changing those would not have
    # a meaningful RoI.
    config = convert_to_app_config(settings)

    setup_logging(
        level=settings.log_level,
        slow_duration=settings.AIODEBUG_SLOW_DURATION_SECS,
        log_format_local_dev_enabled=settings.WEBSERVER_LOG_FORMAT_LOCAL_DEV_ENABLED,
    )

    app = create_application()
    return (app, config)


async def app_factory() -> web.Application:
    """Created to launch app from gunicorn (see docker/boot.sh)"""
    app_settings = ApplicationSettings.create_from_envs()
    assert app_settings.SC_BUILD_TARGET  # nosec

    _logger.info(
        "Application settings: %s", app_settings.json(indent=2, sort_keys=True)
    )

    app, _ = _setup_app_from_settings(app_settings)

    return app


# CLI -------------

main = typer.Typer(name="simcore-service-webserver")

main.command()(
    create_settings_command(settings_cls=ApplicationSettings, logger=_logger)
)

_NO_TRIAL_DAYS: Final[int] = -1


@main.command()
def invitations(
    base_url: str,
    issuer_email: str,
    trial_days: Annotated[int, typer.Argument()] = _NO_TRIAL_DAYS,
    user_id: int = 1,
    num_codes: int = 15,
    code_length: int = 30,
):
    login_cli.invitations(
        base_url=base_url,
        issuer_email=issuer_email,
        trial_days=trial_days if trial_days != _NO_TRIAL_DAYS else None,
        user_id=user_id,
        num_codes=num_codes,
        code_length=code_length,
    )


@main.command()
def run():
    """Runs web server"""
    # NOTE: keeping imports here to reduce CLI load time
    from .application import run_service

    app_settings = ApplicationSettings.create_from_envs()
    app, cfg = _setup_app_from_settings(app_settings)
    run_service(app, cfg)
