# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from uuid import UUID

import pytest
from models_library.projects import Workbench
from pydantic import BaseModel
from simcore_service_webserver.projects import _create

# HELPERS -----------------------------------------------------------------------------------------


class ProjectSelectDB(BaseModel):
    workbench: Workbench


class ProjectRepo:
    def get(self, uuid):
        pass


# TESTS -----------------------------------------------------------------------------------------


@pytest.mark.skip(reason="UNDER DEV")
def test_clone_project(project_uuid: UUID):
    # a project in db
    repo = ProjectRepo()

    # fetch from db -> model
    project: ProjectSelectDB = repo.get(uuid=project_uuid)

    # user copy & update

    # update all references to NodeID using a nodes_map
    new_workbench: Workbench = project.workbench.copy(exclude_unset=True)

    # make a copy & update
    project_clone = project.copy(
        update={"workbench": new_workbench}, exclude_unset=True
    )

    # convert cloned ProjectSelectDB -> ProjectInsertDB
    # retrieve ProjectSelectDB -> ProjectGet
    #


@pytest.mark.skip(reason="UNDER DEV")
def test_long_running_copy_project(app, user_id, heavy_project_uuid):

    task = _create.schedule_task(app, user_id, heavy_project_uuid)

    # TODO: implement a generic response for long running operation from a asyncio.Task
    # https://google.aip.dev/151
