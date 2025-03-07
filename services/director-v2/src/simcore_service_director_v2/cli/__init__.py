import asyncio
import logging
from typing import Final

import rich
import typer
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from settings_library.utils_cli import create_settings_command

from .._meta import PROJECT_NAME
from ..core.settings import AppSettings
from ..modules.osparc_variables import substitutions
from ._close_and_save_service import async_close_and_save_service
from ._core import (
    async_free_service_disk_space,
    async_project_save_state,
    async_project_state,
    async_service_state,
)

DEFAULT_NODE_SAVE_ATTEMPTS: Final[int] = 3
DEFAULT_STATE_UPDATE_INTERVAL_S: Final[int] = 5
DEFAULT_DISABLE_OBSERVATION_ATTEMPTS: Final[int] = 10
DEFAULT_SAVE_STATE_ATTEMPTS: Final[int] = 3
DEFAULT_OUTPUTS_PUSH_ATTEMPTS: Final[int] = 3
DEFAULT_TASK_UPDATE_INTERVAL_S: Final[int] = 1

main = typer.Typer(
    name=PROJECT_NAME,
    pretty_exceptions_enable=False,
    pretty_exceptions_show_locals=False,
)

_logger = logging.getLogger(__name__)

main.command()(create_settings_command(settings_cls=AppSettings, logger=_logger))


@main.command()
def project_save_state(
    project_id: ProjectID, save_attempts: int = DEFAULT_NODE_SAVE_ATTEMPTS
):
    """
    Saves the state of all dy-sidecars in a project.
    In case of error while saving the state of an individual node,
    it will retry to save.
    If errors persist it will produce a list of nodes which failed to save.
    """
    asyncio.run(async_project_save_state(project_id, save_attempts))


@main.command()
def project_state(
    project_id: ProjectID,
    blocking: bool = True,
    update_interval: int = DEFAULT_STATE_UPDATE_INTERVAL_S,
):
    """
    Displays the state of the nodes in the project.
    """
    asyncio.run(async_project_state(project_id, blocking, update_interval))


@main.command()
def service_state(node_id: NodeID):
    """
    Prints the state of a services as tracked by director-v2
    """
    asyncio.run(async_service_state(node_id))


@main.command()
def free_reserved_disk_space(node_id: NodeID):
    """
    Frees service's reserved disk space
    """
    asyncio.run(async_free_service_disk_space(node_id))


@main.command()
def close_and_save_service(
    node_id: NodeID,
    skip_container_removal: bool = False,
    skip_state_saving: bool = False,
    skip_outputs_pushing: bool = False,
    skip_docker_resources_removal: bool = False,
    disable_observation_attempts: int = typer.Option(
        DEFAULT_DISABLE_OBSERVATION_ATTEMPTS,
        help="disable observation retry max attempts",
    ),
    state_save_retry_attempts: int = typer.Option(
        DEFAULT_SAVE_STATE_ATTEMPTS,
        help="state saving retry max attempts",
    ),
    outputs_push_retry_attempts: int = typer.Option(
        DEFAULT_OUTPUTS_PUSH_ATTEMPTS,
        help="outputs pushing retry max attempts",
    ),
    update_interval: int = typer.Option(
        DEFAULT_TASK_UPDATE_INTERVAL_S,
        help="delay between data recovery, used to update the ui",
    ),
):
    """
    Saves the state, the outputs and removes all
    docker created resources for a service.

    Order of actions taken: container removal -> state
    saving -> outputs pushing -> docker resources removal
    and removing service from observation.

    Should work out of the box with current defaults. Below
    options can be used to skip one of these steps and are
    generally intended for edge cases.

    For more: https://github.com/ITISFoundation/osparc-simcore/pull/3430
    """
    asyncio.run(
        async_close_and_save_service(
            node_id,
            skip_container_removal,
            skip_state_saving,
            skip_outputs_pushing,
            skip_docker_resources_removal,
            disable_observation_attempts,
            state_save_retry_attempts,
            outputs_push_retry_attempts,
            update_interval,
        )
    )


@main.command()
def osparc_variables():
    """Lists all registered osparc session variables"""
    for name in substitutions.list_osparc_session_variables():
        rich.print(name)
