""" Misc that does not fit on other modules

Functions/classes that are too small to create a new module or helpers within this plugin's context are placed here

"""

import asyncio
import logging

import aiohttp
from aiohttp import ClientTimeout, web
from models_library.projects import ProjectID

from ._abc import AbstractProjectRunPolicy, CommitID
from .settings import DirectorV2Settings, get_client_session, get_plugin_settings

log = logging.getLogger(__name__)


SERVICE_HEALTH_CHECK_TIMEOUT = ClientTimeout(total=2, connect=1)


async def is_healthy(app: web.Application) -> bool:
    try:
        session = get_client_session(app)
        settings: DirectorV2Settings = get_plugin_settings(app)
        health_check_url = settings.base_url.parent
        await session.get(
            url=health_check_url,
            ssl=False,
            raise_for_status=True,
            timeout=SERVICE_HEALTH_CHECK_TIMEOUT,
        )
        return True
    except (aiohttp.ClientError, asyncio.TimeoutError) as err:
        # SEE https://docs.aiohttp.org/en/stable/client_reference.html#hierarchy-of-exceptions
        log.warning("Director is NOT healthy: %s", err)
        return False


class DefaultProjectRunPolicy(AbstractProjectRunPolicy):
    # pylint: disable=unused-argument

    async def get_runnable_projects_ids(
        self,
        request: web.Request,
        project_uuid: ProjectID,
    ) -> list[ProjectID]:
        return [
            project_uuid,
        ]

    async def get_or_create_runnable_projects(
        self,
        request: web.Request,
        project_uuid: ProjectID,
    ) -> tuple[list[ProjectID], list[CommitID]]:
        """
        Returns ids and refid of projects that can run
        If project_uuid is a std-project, then it returns itself
        If project_uuid is a meta-project, then it returns iterations
        """
        return (
            [
                project_uuid,
            ],
            [],
        )
