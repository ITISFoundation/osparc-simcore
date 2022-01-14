import logging

import typer
from settings_library.utils_cli import create_settings_command

from . import application
from .settings import Settings

LOG_LEVEL_STEP = logging.CRITICAL - logging.ERROR

log = logging.getLogger(__name__)

main = typer.Typer(name="simcore-service-storage service")

main.command()(create_settings_command(settings_cls=Settings, logger=log))


@main.command()
def run():
    """Runs application"""
    typer.secho("Resolving settings ...", nl=False)
    settings_obj = Settings.create_from_envs()
    typer.secho("DONE", fg=typer.colors.GREEN)

    logging.basicConfig(level=settings_obj.log_level)
    logging.root.setLevel(settings_obj.log_level)

    # keep mostly quiet noisy loggers
    quiet_level: int = max(
        min(logging.root.level + LOG_LEVEL_STEP, logging.CRITICAL), logging.WARNING
    )
    logging.getLogger("engineio").setLevel(quiet_level)
    logging.getLogger("openapi_spec_validator").setLevel(quiet_level)
    logging.getLogger("sqlalchemy").setLevel(quiet_level)
    logging.getLogger("sqlalchemy.engine").setLevel(quiet_level)

    typer.secho("Starting app ... ")
    application.run(settings_obj)
