import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import typer
from common_library.json_serialization import json_dumps
from fastapi import FastAPI
from servicelib.long_running_tasks.models import TaskProgress
from settings_library.utils_cli import create_settings_command

from ._meta import PROJECT_NAME
from .core.application import create_base_app
from .core.settings import ApplicationSettings
from .modules.long_running_tasks import task_ports_outputs_push, task_save_state
from .modules.mounted_fs import MountedVolumes, setup_mounted_fs
from .modules.outputs import OutputsManager, setup_outputs

log = logging.getLogger(__name__)
main = typer.Typer(
    name=PROJECT_NAME,
    pretty_exceptions_enable=False,
    pretty_exceptions_show_locals=False,
)


main.command()(create_settings_command(settings_cls=ApplicationSettings, logger=log))


@main.command()
def openapi():
    """Prints OpenAPI specifications in json format"""
    app = create_base_app()
    typer.secho(json_dumps(app.openapi(), indent=2))


@asynccontextmanager
async def _initialized_app() -> AsyncIterator[FastAPI]:
    app = create_base_app()

    # setup MountedVolumes
    setup_mounted_fs(app)
    setup_outputs(app)

    await app.router.startup()
    yield app
    await app.router.shutdown()


def _print_highlight(message: str) -> None:
    typer.echo(typer.style(message, fg=typer.colors.MAGENTA))


@main.command()
def state_list_dirs():
    """Lists files inside state directories"""

    async def _async_state_list_dirs() -> None:
        async with _initialized_app() as app:
            mounted_volumes: MountedVolumes = app.state.mounted_volumes
            for state_path in mounted_volumes.state_paths:
                state_path_content = list(state_path.glob("*"))
                typer.echo(f"Entries in {state_path}: {state_path_content}")

    asyncio.run(_async_state_list_dirs())


@main.command()
def state_save():
    """Saves the state, usually workspace directory"""

    async def _async_save_state() -> None:
        async with _initialized_app() as app:
            settings: ApplicationSettings = app.state.settings
            mounted_volumes: MountedVolumes = app.state.mounted_volumes

            await task_save_state(TaskProgress.create(), settings, mounted_volumes, app)

    asyncio.run(_async_save_state())
    _print_highlight("state save finished successfully")


@main.command()
def outputs_push():
    """Pushes the output ports"""

    async def _async_outputs_push() -> None:
        async with _initialized_app() as app:
            outputs_manager: OutputsManager = app.state.outputs_manager
            await task_ports_outputs_push(TaskProgress.create(), outputs_manager, app)

    asyncio.run(_async_outputs_push())
    _print_highlight("output ports push finished successfully")


#
# NOTE: We intentionally did NOT create a command to run the application
# Use instead $ uvicorn --factory simcore_service_dynamic_sidecar.main:app_factory
#
