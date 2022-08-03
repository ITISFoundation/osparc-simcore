import asyncio
import json
import logging

import typer
from fastapi import FastAPI
from servicelib.fastapi.long_running_tasks.server import TaskProgress
from settings_library.utils_cli import create_settings_command
from simcore_service_dynamic_sidecar.core.application import create_base_app
from simcore_service_dynamic_sidecar.core.rabbitmq import RabbitMQ
from simcore_service_dynamic_sidecar.core.settings import ApplicationSettings
from simcore_service_dynamic_sidecar.modules.long_running_tasks import (
    task_ports_outputs_push,
    task_save_state,
)
from simcore_service_dynamic_sidecar.modules.mounted_fs import (
    MountedVolumes,
    setup_mounted_fs,
)

from ._meta import PROJECT_NAME
from .core.settings import ApplicationSettings

log = logging.getLogger(__name__)
main = typer.Typer(name=PROJECT_NAME)


main.command()(create_settings_command(settings_cls=ApplicationSettings, logger=log))


@main.command()
def openapi():
    """Prints OpenAPI specifications in json format"""
    app = create_base_app()
    typer.secho(json.dumps(app.openapi(), indent=2))


async def _setup_app_for_task_execution() -> FastAPI:
    app = create_base_app()

    # setup MountedVolumes
    setup_mounted_fs(app)

    # setup RabbitMQ
    app.state.rabbitmq = RabbitMQ(app)
    await app.state.rabbitmq.connect()

    return app


def _print_highlight(message: str) -> None:
    typer.echo(typer.style(message, fg=typer.colors.MAGENTA))


@main.command()
def state_save():
    """Saves the state, usually workspace directory"""

    async def _async_save_state() -> None:
        app = await _setup_app_for_task_execution()

        settings: ApplicationSettings = app.state.settings
        mounted_volumes: MountedVolumes = app.state.mounted_volumes
        rabbitmq: RabbitMQ = app.state.rabbitmq

        await task_save_state(
            TaskProgress.create(), settings, mounted_volumes, rabbitmq
        )

    asyncio.get_event_loop().run_until_complete(_async_save_state())
    _print_highlight("state save finished successfully")


@main.command()
def outputs_push():
    """Pushes the output ports"""

    async def _async_save_state() -> None:
        app = await _setup_app_for_task_execution()

        mounted_volumes: MountedVolumes = app.state.mounted_volumes
        rabbitmq: RabbitMQ = app.state.rabbitmq

        await task_ports_outputs_push(
            TaskProgress.create(), None, mounted_volumes, rabbitmq
        )

    asyncio.get_event_loop().run_until_complete(_async_save_state())
    _print_highlight("output ports push finished successfully")


#
# NOTE: We intentionally did NOT create a command to run the application
# Use instead $ uvicorn simcore_service_dynamic_sidecar.main:the_app
#
