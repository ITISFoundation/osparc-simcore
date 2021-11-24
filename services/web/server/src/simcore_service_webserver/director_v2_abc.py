from abc import ABC, abstractmethod
from typing import List, Optional, Tuple

from aiohttp import web
from models_library.projects import ProjectID

CommitID = int
_APP_PROJECT_RUN_POLICY_KEY = f"{__name__}.ProjectRunPolicy"


class AbstractProjectRunPolicy(ABC):
    """
    Since the introduction of meta-projects, not all
    projects can be executed "as is". E.g. a meta-project
    with an iterator needs to be converted to a project that
    replaces the iterator node with a concrete
    iteration value so it can be run.

    This policy class intends to fill this gap by resolving which
    runnable/s project/s are associated to a given project (by it's project_uuid)

    For instance, if project_uuid is a standard project, then it returns itself
    but if project_uuid is a meta-project, then it returns iterations

    NOTE: this abstraction is used to change the functionality of
    the ``director_v2`` app module while keeping it decoupled from
    higher level add-ons like the ``meta`` app module
    """

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

        ...


def get_project_run_policy(app: web.Application) -> Optional[AbstractProjectRunPolicy]:
    return app.get(_APP_PROJECT_RUN_POLICY_KEY)


def set_project_run_policy(app: web.Application, policy_obj: AbstractProjectRunPolicy):
    app[_APP_PROJECT_RUN_POLICY_KEY] = policy_obj
