# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict
from uuid import UUID

import jsonschema
import pytest
from jsonschema import ValidationError
from models_library.projects import Workbench
from pydantic import BaseModel
from simcore_service_webserver.projects import _create
from simcore_service_webserver.projects.project_models import ProjectDict

# HELPERS -----------------------------------------------------------------------------------------


class ProjectSelectDB(BaseModel):
    workbench: Workbench


class ProjectRepo:
    def get(self, uuid):
        pass


# TESTS -----------------------------------------------------------------------------------------


@pytest.fixture
def project_schema(project_schema_file: Path) -> Dict[str, Any]:
    with open(project_schema_file) as fh:
        schema = json.load(fh)
    return schema


@pytest.mark.parametrize(
    "test_data_file_name",
    [
        "fake-project.json",
        "fake-template-projects.hack08.notebooks.json",
        "fake-template-projects.isan.2dplot.json",
        "fake-template-projects.isan.matward.json",
        "fake-template-projects.isan.paraview.json",
        "fake-template-projects.isan.ucdavis.json",
        "fake-template-projects.sleepers.json",
    ],
)
def test_clone_project_row(
    test_data_file_name: str,
    project_schema: Dict[str, Any],
    tests_data_dir: Path,
    app,
    user_id,
):
    original_project: ProjectDict = json.loads(
        (tests_data_dir / test_data_file_name).read_text()
    )

    source_project: ProjectDict = deepcopy(original_project)
    clone, _ = _create.clone_project(
        app, user_id, source_project, new_project_id=_create.AUTO_CREATE_UUID
    )

    # was not modified by clone_project_document
    assert source_project == original_project

    # valid clone
    assert clone["uuid"] != original_project["uuid"]

    node_ids = original_project["workbench"].keys()
    for clone_node_id in clone["workbench"]:
        assert clone_node_id not in node_ids

    try:
        jsonschema.validate(instance=clone, schema=project_schema)
    except ValidationError as err:
        pytest.fail(f"Invalid clone of '{test_data_file_name}': {err.message}")


@pytest.mark.skip(reason="UNDER DEV")
def test_clone_project_dev(project_uuid: UUID):
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
