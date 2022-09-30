import asyncio
import logging
from typing import Final

import typer
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from settings_library.utils_cli import create_settings_command

from ..core.settings import AppSettings
from ..meta import PROJECT_NAME
from .core import async_node_save_state, async_project_save_state, async_project_state

DEFAULT_NODE_SAVE_RETRY: Final[int] = 3
DEFAULT_STATE_UPDATE_INTERVAL: Final[int] = 5

main = typer.Typer(name=PROJECT_NAME)

log = logging.getLogger(__name__)
main.command()(create_settings_command(settings_cls=AppSettings, logger=log))


@main.command()
def project_save_state(
    project_id: ProjectID, retry_save: int = DEFAULT_NODE_SAVE_RETRY
):
    """
    Saves the state of all dy-sidecars in a project.
    In case of error while saving the state of an individual node,
    it will retry to save.
    If errors persist it will produce a list of nodes which failed to save.
    """
    asyncio.run(async_project_save_state(project_id, retry_save))


@main.command()
def node_save_state(node_id: NodeID, retry_save: int = DEFAULT_NODE_SAVE_RETRY):
    """
    Saves the state of an individual node in the project.
    """
    asyncio.run(async_node_save_state(node_id, retry_save))


@main.command()
def project_state(
    project_id: ProjectID,
    blocking: bool = True,
    update_interval: int = DEFAULT_STATE_UPDATE_INTERVAL,
):
    """
    Displays the state of the nodes in the project.
    """
    asyncio.run(async_project_state(project_id, blocking, update_interval))
