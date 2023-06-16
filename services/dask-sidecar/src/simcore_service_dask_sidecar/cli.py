import logging

import typer
from settings_library.utils_cli import create_settings_command, create_version_callback

from ._meta import PROJECT_NAME, __version__
from .settings import Settings

# SEE setup entrypoint 'simcore_service_dask_sidecar.cli:the_app'
_logger = logging.getLogger(__name__)

main = typer.Typer(name=PROJECT_NAME)

#
# COMMANDS
#
main.callback()(create_version_callback(__version__))
main.command()(create_settings_command(settings_cls=Settings, logger=_logger))
