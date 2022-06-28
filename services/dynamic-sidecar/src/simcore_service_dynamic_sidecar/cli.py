import json
import logging

import typer
from settings_library.utils_cli import create_settings_command
from simcore_service_dynamic_sidecar.core.application import create_basic_app

from ._meta import PROJECT_NAME
from .core.settings import DynamicSidecarSettings

log = logging.getLogger(__name__)
main = typer.Typer(name=PROJECT_NAME)


main.command()(create_settings_command(settings_cls=DynamicSidecarSettings, logger=log))


@main.command()
def openapi():
    """Prints OpenAPI specifications in json format"""
    app = create_basic_app()
    typer.secho(json.dumps(app.openapi(), indent=2))


#
# NOTE: We intentionally did NOT create a command to run the application
# Use instead $ uvicorn simcore_service_dynamic_sidecar.main:app
#
