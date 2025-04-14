"""Misc that does not fit on other modules

Functions/classes that are too small to create a new module or helpers within this plugin's context are placed here

"""

import logging

from aiohttp import web
from models_library.projects import ProjectID

from ._abc import AbstractProjectRunPolicy, CommitID

log = logging.getLogger(__name__)


class DefaultProjectRunPolicy(AbstractProjectRunPolicy):
    # pylint: disable=unused-argument

    async def get_runnable_projects_ids(
        self,
        request: web.Request,
        project_uuid: ProjectID,
    ) -> list[ProjectID]:
        assert request  # nosec
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
        assert request  # nosec
        return (
            [
                project_uuid,
            ],
            [],
        )
