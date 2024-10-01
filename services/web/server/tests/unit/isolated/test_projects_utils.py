# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import json
from copy import deepcopy
from pathlib import Path

import pytest
from models_library.projects import Project
from models_library.projects_nodes_io import NodeID
from simcore_service_webserver.projects.models import ProjectDict
from simcore_service_webserver.projects.nodes_utils import project_get_depending_nodes
from simcore_service_webserver.projects.utils import (
    any_node_inputs_changed,
    clone_project_document,
    default_copy_project_name,
)


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
def test_clone_project_document(
    test_data_file_name: str,
    tests_data_dir: Path,
):
    original_project: ProjectDict = json.loads(
        (tests_data_dir / test_data_file_name).read_text()
    )

    source_project: ProjectDict = deepcopy(original_project)
    clone, _ = clone_project_document(source_project)

    # was not modified by clone_project_document
    assert source_project == original_project

    # valid clone
    assert clone["uuid"] != original_project["uuid"]

    node_ids = original_project["workbench"].keys()
    for clone_node_id in clone["workbench"]:
        assert clone_node_id not in node_ids

    # Here we do not use anymore jsonschema.validator since ...
    #
    # "OpenAPI 3.0 does not have an explicit null type as in JSON Schema, but you can use nullable:
    # true to specify that the value may be null. Note that null is different from an empty string."
    #
    # SEE https://swagger.io/docs/specification/data-models/data-types/#Null

    assert Project.model_validate(clone) is not None


@pytest.mark.parametrize(
    "node_uuid, expected_dependencies",
    [
        (
            NodeID("b4b20476-e7c0-47c2-8cc4-f66ac21a13bf"),
            {
                NodeID("5739e377-17f7-4f09-a6ad-62659fb7fdec"),
            },
        ),
        (NodeID("5739e377-17f7-4f09-a6ad-62659fb7fdec"), set()),
        (NodeID("351fd505-1ee3-466d-ad6c-ea2915ffd364"), set()),
    ],
)
async def test_project_get_depending_nodes(
    fake_project: ProjectDict, node_uuid: NodeID, expected_dependencies: set[NodeID]
):
    set_of_depending_nodes = await project_get_depending_nodes(fake_project, node_uuid)
    assert set_of_depending_nodes == expected_dependencies


def test_any_node_inputs_changed(fake_project: ProjectDict):
    current_project = deepcopy(fake_project)
    updated_project = deepcopy(fake_project)

    assert not any_node_inputs_changed(updated_project, current_project)

    assert (
        fake_project == current_project
    ), "any_node_inputs_changed MUST NOT modify data "
    assert (
        fake_project == updated_project
    ), "any_node_inputs_changed MUST NOT modify data"

    # add new node w/ a link
    fake_node = deepcopy(
        fake_project["workbench"]["5739e377-17f7-4f09-a6ad-62659fb7fdec"]
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


@pytest.mark.parametrize(
    "original_name, expected_copy_suffix",
    [
        ("", " (Copy)"),
        ("whatever is whatever", "whatever is whatever (Copy)"),
        ("(Copy)", "(Copy) (Copy)"),
        (
            "some project cool name with 123 numbers (Copy)",
            "some project cool name with 123 numbers (Copy)(1)",
        ),
        (" (Copy)(2)", " (Copy)(3)"),
        (" (Copy)(456)", " (Copy)(457)"),
    ],
)
def test_default_copy_project_name(original_name: str, expected_copy_suffix: str):
    received_name = default_copy_project_name(original_name)
    assert received_name == expected_copy_suffix


def test_validate_project_json_schema():
    CURRENT_DIR = Path(__file__).resolve().parent

    with open(CURRENT_DIR / "data/project-data.json") as f:
        project: ProjectDict = json.load(f)

    Project.model_validate(project)
