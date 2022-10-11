import asyncio
import logging
from typing import Final

import typer
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from settings_library.utils_cli import create_settings_command

from ..core.settings import AppSettings
from ..meta import PROJECT_NAME
from ._core import async_node_save_state, async_project_save_state, async_project_state
from ._close_and_save_service import async_close_and_save_service

DEFAULT_NODE_SAVE_RETRY_TIMES: Final[int] = 3
DEFAULT_STATE_UPDATE_INTERVAL_S: Final[int] = 5
DEFAULT_SAVE_STATE_RETRY_TIMES: Final[int] = 3
DEFAULT_OUTPUTS_PUSH_RETRY_TIMES: Final[int] = 3
DEFAULT_TASK_UPDATE_INTERVAL_S: Final[int] = 1

main = typer.Typer(name=PROJECT_NAME)

log = logging.getLogger(__name__)
main.command()(create_settings_command(settings_cls=AppSettings, logger=log))


@main.command()
def project_save_state(
    project_id: ProjectID, save_retry_times: int = DEFAULT_NODE_SAVE_RETRY_TIMES
):
    """
    Saves the state of all dy-sidecars in a project.
    In case of error while saving the state of an individual node,
    it will retry to save.
    If errors persist it will produce a list of nodes which failed to save.
    """
    asyncio.run(async_project_save_state(project_id, save_retry_times))


@main.command()
def node_save_state(node_id: NodeID, retry_save: int = DEFAULT_NODE_SAVE_RETRY_TIMES):
    """
    Saves the state of an individual node in the project.
    """
    asyncio.run(async_node_save_state(node_id, retry_save))


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
def close_and_save_service(
    node_id: NodeID,
    skip_container_removal: bool = False,
    skip_state_saving: bool = False,
    skip_outputs_pushing: bool = False,
    skip_docker_resources_removal: bool = False,
    state_retry: int = typer.Option(
        DEFAULT_SAVE_STATE_RETRY_TIMES,
        help="times the state saving will be retried if failed",
    ),
    outputs_retry: int = typer.Option(
        DEFAULT_OUTPUTS_PUSH_RETRY_TIMES,
        help="times the outputs pushing will be retried if failed",
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
    saving -> outputs pushing -> docker resources removal.

    Should work out of the box with current defaults. Below
    options can be used to skip one of these steps and are
    generally intended for edge cases.
    """
    asyncio.run(
        async_close_and_save_service(
            node_id,
            skip_container_removal,
            skip_state_saving,
            skip_outputs_pushing,
            skip_docker_resources_removal,
            state_retry,
            outputs_retry,
            update_interval,
        )
    )
