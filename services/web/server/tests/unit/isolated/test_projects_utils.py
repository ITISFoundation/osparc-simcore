# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Set

import jsonschema
import pytest
from jsonschema import ValidationError
from simcore_service_webserver._resources import resources
from simcore_service_webserver.projects.project_models import ProjectDict
from simcore_service_webserver.projects.projects_utils import (
    any_node_inputs_changed,
    clone_project_document,
    project_get_depending_nodes,
)


def load_template_projects() -> Dict[str, Any]:
    projects = []
    projects_names = [
        name for name in resources.listdir("data") if "template-projects" in name
    ]
    for name in projects_names:
        with resources.stream(f"data/{name}") as fp:
            projects.extend(json.load(fp))
    return projects


@pytest.fixture
def project_schema(project_schema_file: Path) -> Dict[str, Any]:
    with open(project_schema_file) as fh:
        schema = json.load(fh)
    return schema


@pytest.mark.parametrize(
    "name,project", [(p["name"], p) for p in load_template_projects()]
)
def test_clone_project_document(
    name: str, project: Dict[str, Any], project_schema: Dict[str, Any]
):

    source = deepcopy(project)
    clone, _ = clone_project_document(source)

    # was not modified by clone_project_document
    assert source == project

    # valid clone
    assert clone["uuid"] != project["uuid"]

    node_ids = project["workbench"].keys()
    for clone_node_id in clone["workbench"]:
        assert clone_node_id not in node_ids

    try:
        jsonschema.validate(instance=clone, schema=project_schema)
    except ValidationError as err:
        pytest.fail(f"Invalid clone of '{name}': {err.message}")


@pytest.mark.parametrize(
    "node_uuid, expected_dependencies",
    [
        (
            "b4b20476-e7c0-47c2-8cc4-f66ac21a13bf",
            {
                "5739e377-17f7-4f09-a6ad-62659fb7fdec",
            },
        ),
        ("5739e377-17f7-4f09-a6ad-62659fb7fdec", set()),
        ("351fd505-1ee3-466d-ad6c-ea2915ffd364", set()),
    ],
)
async def test_project_get_depending_nodes(
    fake_project_data: ProjectDict, node_uuid: str, expected_dependencies: Set[str]
):
    set_of_depending_nodes = await project_get_depending_nodes(
        fake_project_data, node_uuid
    )
    assert set_of_depending_nodes == expected_dependencies


def test_any_node_inputs_changed(fake_project_data: ProjectDict):

    current_project = deepcopy(fake_project_data)
    updated_project = deepcopy(fake_project_data)

    assert not any_node_inputs_changed(updated_project, current_project)

    assert (
        fake_project_data == current_project
    ), "any_node_inputs_changed MUST NOT modify data "
    assert (
        fake_project_data == updated_project
    ), "any_node_inputs_changed MUST NOT modify data"

    # add new node w/ a link
    fake_node = deepcopy(
        fake_project_data["workbench"]["5739e377-17f7-4f09-a6ad-62659fb7fdec"]
    )
    assert fake_node["inputs"] == {
        "Na": 0,
        "Kr": 0,
        "BCL": 200,
        "NBeats": 5,
        "Ligand": 0,
        "cAMKII": "WT",
        "initfile": {
            "nodeUuid": "b4b20476-e7c0-47c2-8cc4-f66ac21a13bf",
            "output": "outFile",
        },
    }

    updated_project["workbench"]["15d79982-9273-435b-bab6-e5366ba19165"] = fake_node

    assert any_node_inputs_changed(updated_project, current_project)

    # add new node w/o a link
    fake_node["inputs"].pop("initfile")
    assert not any_node_inputs_changed(updated_project, current_project)
