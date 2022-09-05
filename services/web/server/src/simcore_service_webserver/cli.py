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
from typing import Any

import typer
from aiohttp import web
from settings_library.utils_cli import create_settings_command

from .application import create_application, run_service
from .application_settings import ApplicationSettings
from .application_settings_utils import convert_to_app_config
from .log import setup_logging

# ptsvd cause issues with ProcessPoolExecutor
# SEE: https://github.com/microsoft/ptvsd/issues/1443
if os.environ.get("SC_BOOT_MODE") == "debug-ptvsd":
    import multiprocessing

    multiprocessing.set_start_method("spawn", True)

log = logging.getLogger(__name__)


def _setup_app_from_settings(
    settings: ApplicationSettings,
) -> tuple[web.Application, dict[str, Any]]:

    # NOTE: keeping an equivalent config allows us
    # to keep some of the code from the previous
    # design whose starting point was a validated
    # config. E.g. many test fixtures were based on
    # given configs and changing those would not have
    # a meaningful RoI.
    config = convert_to_app_config(settings)

    setup_logging(
        level=settings.log_level,
        slow_duration=settings.AIODEBUG_SLOW_DURATION_SECS,
    )

    app = create_application()
    return (app, config)


async def app_factory() -> web.Application:
    """Created to launch app from gunicorn (see docker/boot.sh)"""
    app_settings = ApplicationSettings()
    assert app_settings.SC_BUILD_TARGET  # nosec

    log.info("Application settings: %s", app_settings.json(indent=2, sort_keys=True))

    app, _ = _setup_app_from_settings(app_settings)

    return app


# CLI -------------

main = typer.Typer(name="simcore-service-webserver")

main.command()(create_settings_command(settings_cls=ApplicationSettings, logger=log))


@main.command()
def run():
    app_settings = ApplicationSettings()
    app, cfg = _setup_app_from_settings(app_settings)
    run_service(app, cfg)
