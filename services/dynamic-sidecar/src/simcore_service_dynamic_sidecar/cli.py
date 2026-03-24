import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

import typer
from asgi_lifespan import LifespanManager
from common_library.json_serialization import json_dumps
from fastapi import FastAPI
from servicelib.long_running_tasks.models import TaskProgress
from settings_library.utils_cli import create_settings_command

from ._meta import PROJECT_NAME
from .core.application import create_base_app
from .core.rabbitmq import setup_rabbitmq
from .core.settings import ApplicationSettings
from .modules.long_running_tasks import (
    push_user_services_output_ports,
    save_user_services_state_paths,
)
from .modules.mounted_fs import MountedVolumes, setup_mounted_fs
from .modules.outputs import OutputsManager, setup_outputs
from .modules.r_clone_mount_manager import setup_r_clone_mount_manager

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
async def _initialized_app(
    *,
    with_rabbitmq: bool = False,
    with_mounted_fs: bool = False,
    with_outputs: bool = False,
    with_r_clone_mount_manager: bool = False,
) -> AsyncIterator[FastAPI]:
    app = create_base_app()

    # setup required components
    if with_rabbitmq:
        setup_rabbitmq(app)
    if with_mounted_fs:
        setup_mounted_fs(app)
    if with_outputs:
        setup_outputs(app)
    if with_r_clone_mount_manager:
        setup_r_clone_mount_manager(app)

    async with LifespanManager(app):
        yield app


def _print_highlight(message: str) -> None:
    typer.echo(typer.style(message, fg=typer.colors.MAGENTA))


@main.command()
def state_list_dirs():
    """Lists files inside state directories"""

    async def _async_state_list_dirs() -> None:
        async with _initialized_app(with_mounted_fs=True) as app:
            mounted_volumes: MountedVolumes = app.state.mounted_volumes
            for state_path in mounted_volumes.state_paths:
                state_path_content = list(state_path.glob("*"))
                typer.echo(f"Entries in {state_path}: {state_path_content}")

    asyncio.run(_async_state_list_dirs())


@main.command()
def state_save(*, enable_rabbitmq: Annotated[bool, typer.Option(help="allows to disable rabbitmq setup")] = True):
    """Saves the state, usually workspace directory

    NOTE: if rabbitmq is causing issues it's possible to disable the setup (not necessary for this command)
    """

    async def _async_save_state() -> None:
        async with _initialized_app(
            with_rabbitmq=enable_rabbitmq, with_mounted_fs=True, with_r_clone_mount_manager=True
        ) as app:
            settings: ApplicationSettings = app.state.settings
            mounted_volumes: MountedVolumes = app.state.mounted_volumes

            await save_user_services_state_paths(
                TaskProgress.create(),
                app=app,
                settings=settings,
                mounted_volumes=mounted_volumes,
            )

    asyncio.run(_async_save_state())
    _print_highlight("state save finished successfully")


@main.command()
def outputs_push(*, enable_rabbitmq: Annotated[bool, typer.Option(help="allows to disable rabbitmq setup")] = True):
    """Pushes the output ports

    NOTE: if rabbitmq is causing issues it's possible to disable the setup (not necessary for this command)
    """

    async def _async_outputs_push() -> None:
        async with _initialized_app(with_rabbitmq=enable_rabbitmq, with_mounted_fs=True, with_outputs=True) as app:
            outputs_manager: OutputsManager = app.state.outputs_manager
            await push_user_services_output_ports(TaskProgress.create(), app=app, outputs_manager=outputs_manager)

    asyncio.run(_async_outputs_push())
    _print_highlight("output ports push finished successfully")


#
# NOTE: We intentionally did NOT create a command to run the application
# Use instead $ uvicorn --factory simcore_service_dynamic_sidecar.main:app_factory
#
