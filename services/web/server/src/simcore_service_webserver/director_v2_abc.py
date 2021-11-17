from abc import ABC, abstractmethod
from typing import List, Optional, Tuple

from aiohttp import web
from models_library.projects import ProjectID

CommitID = int


class AbstractProjectRunPolicy(ABC):
    # pylint: disable=unused-argument

    @abstractmethod
    async def get_runnable_projects_ids(
        self,
        request: web.Request,
        project_uuid: ProjectID,
    ) -> List[ProjectID]:
        ...

    @abstractmethod
    async def get_or_create_runnable_projects(
        self,
        request: web.Request,
        project_uuid: ProjectID,
    ) -> Tuple[List[ProjectID], List[CommitID]]:
        """
        Returns ids and refid of projects that can run
        If project_uuid is a std-project, then it returns itself
        If project_uuid is a meta-project, then it returns iterations
        """
        ...


def get_run_policy(app: web.Application) -> Optional[AbstractProjectRunPolicy]:
    return app.get(f"{__name__}.ProjectRunPolicy")


def set_run_policy(app: web.Application, policy_obj: AbstractProjectRunPolicy):
    app[f"{__name__}.ProjectRunPolicy"] = policy_obj
