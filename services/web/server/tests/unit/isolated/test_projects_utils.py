# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import json
from copy import deepcopy
from pathlib import Path

import pytest
from faker import Faker
from models_library.projects import Project
from models_library.projects_nodes_io import NodeID
from simcore_service_webserver.projects._crud_api_create import _remap_port_links
from simcore_service_webserver.projects.models import ProjectDict
from simcore_service_webserver.projects.nodes_utils import project_get_depending_nodes
from simcore_service_webserver.projects.utils import (
    NodesMap,
    clone_project_document,
    default_copy_project_name,
    remap_file_link_paths,
)


@pytest.mark.parametrize(
    "test_data_file_name",
    [
        "fake-project.json",
        "fake-project-with-conversation.json",
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
    original_project: ProjectDict = json.loads((tests_data_dir / test_data_file_name).read_text())

    source_project: ProjectDict = deepcopy(original_project)
    clone, _ = clone_project_document(source_project)

    # was not modified by clone_project_document
    assert source_project == original_project

    # valid clone
    assert clone["uuid"] != original_project["uuid"]

    node_ids = original_project["workbench"].keys()
    for clone_node_id in clone["workbench"]:
        assert clone_node_id not in node_ids

    # checks no conversation have been copied
    if "ui" in clone and "annotations" in clone["ui"]:
        assert not any(annotation["type"] == "conversation" for annotation in clone["ui"]["annotations"].values())

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

    with (CURRENT_DIR / "data/project-data.json").open() as f:
        project: ProjectDict = json.load(f)

    Project.model_validate(project)


def test_remap_port_links_remaps_node_uuid():
    old_uuid = "b4b20476-e7c0-47c2-8cc4-f66ac21a13bf"
    new_uuid = "aaaaaaaa-0000-0000-0000-000000000001"
    nodes_map = {old_uuid: new_uuid}

    inputs = {
        "in_1": {"nodeUuid": old_uuid, "output": "outFile"},
        "in_2": 42,
    }

    result = _remap_port_links(inputs, nodes_map)
    assert result is not None
    assert result["in_1"]["nodeUuid"] == new_uuid
    assert result["in_1"]["output"] == "outFile"
    assert result["in_2"] == 42


def test_remap_port_links_unknown_uuid_is_preserved():
    unknown = "cccccccc-0000-0000-0000-000000000099"
    inputs = {"in_1": {"nodeUuid": unknown, "output": "x"}}
    result = _remap_port_links(inputs, nodes_map={})
    assert result is not None
    assert result["in_1"]["nodeUuid"] == unknown


def test_remap_port_links_none_and_empty():
    assert _remap_port_links(None, {}) is None
    assert _remap_port_links({}, {}) == {}


#
# remap_file_link_paths
#


def test_remap_file_link_paths_rewrites_simcore_links(faker: Faker):
    src_uuid = f"{faker.uuid4()}"
    dst_uuid = f"{faker.uuid4()}"
    old_node = f"{faker.uuid4()}"
    new_node = f"{faker.uuid4()}"
    nodes_map: NodesMap = {old_node: new_node}

    inputs = {
        "input_1": {"store": 0, "path": f"{src_uuid}/{old_node}/input.dat", "label": "file"},
        "in_2": 42,
    }
    outputs = {
        "output_1": [
            {"store": 0, "path": f"{src_uuid}/{old_node}/outputs/output_1/parameters.json"},
        ],
        "output_2": [[{"store": 0, "path": f"{src_uuid}/{old_node}/deep/b.dat"}]],
    }

    remapped_inputs = remap_file_link_paths(
        inputs, source_project_uuid=src_uuid, destination_project_uuid=dst_uuid, nodes_map=nodes_map
    )
    remapped_outputs = remap_file_link_paths(
        outputs, source_project_uuid=src_uuid, destination_project_uuid=dst_uuid, nodes_map=nodes_map
    )

    assert remapped_inputs is not None
    assert remapped_inputs["input_1"]["path"] == f"{dst_uuid}/{new_node}/input.dat"
    assert remapped_inputs["input_1"]["label"] == "file"  # other fields preserved
    assert remapped_inputs["in_2"] == 42
    assert remapped_outputs is not None
    assert remapped_outputs["output_1"][0]["path"] == f"{dst_uuid}/{new_node}/outputs/output_1/parameters.json"
    assert remapped_outputs["output_2"][0][0]["path"] == f"{dst_uuid}/{new_node}/deep/b.dat"

    # input not mutated
    assert inputs["input_1"]["path"] == f"{src_uuid}/{old_node}/input.dat"
    assert outputs["output_1"][0]["path"] == f"{src_uuid}/{old_node}/outputs/output_1/parameters.json"
    assert outputs["output_2"][0][0]["path"] == f"{src_uuid}/{old_node}/deep/b.dat"


def test_remap_file_link_paths_accepts_legacy_str_store(faker: Faker):
    src_uuid = f"{faker.uuid4()}"
    dst_uuid = f"{faker.uuid4()}"
    old_node = f"{faker.uuid4()}"
    new_node = f"{faker.uuid4()}"
    nodes_map: NodesMap = {old_node: new_node}

    inputs = {"input_1": {"store": "0", "path": f"{src_uuid}/{old_node}/f.dat"}}
    result = remap_file_link_paths(
        inputs, source_project_uuid=src_uuid, destination_project_uuid=dst_uuid, nodes_map=nodes_map
    )
    assert result is not None
    assert result["input_1"]["path"] == f"{dst_uuid}/{new_node}/f.dat"


def test_remap_file_link_paths_leaves_other_references_untouched(faker: Faker):
    src_uuid = f"{faker.uuid4()}"
    other_project = f"{faker.uuid4()}"
    old_node = f"{faker.uuid4()}"
    unknown_node = f"{faker.uuid4()}"
    nodes_map: NodesMap = {old_node: f"{faker.uuid4()}"}

    inputs = {
        "port_link": {"nodeUuid": old_node, "output": "output_1"},
        "download_link": {"downloadLink": "https://example.com/f", "label": "f"},
        "other_project_path": {"store": 0, "path": f"{other_project}/{old_node}/f.dat"},
        "unknown_node_path": {"store": 0, "path": f"{src_uuid}/{unknown_node}/f.dat"},
        "datcore_link": {"store": 1, "path": f"N:package:{faker.uuid4()}", "dataset": "ds"},
        # a link is only rewritten at a port's top level or inside a list, never
        # inside an opaque dict value: the storage copy does not relocate it there
        "dict_nested_link": {"meta": {"store": 0, "path": f"{src_uuid}/{old_node}/f.dat"}},
        # fewer than the 3 path sections means no remainder to carry over
        "short_path": {"store": 0, "path": f"{src_uuid}/{old_node}"},
        # object ports carry arbitrary JSON: a dict/list store must not raise
        "object_port_dict_store": {"path": "settings.json", "store": {"region": "local"}},
        "object_port_list_store": {"path": "settings.json", "store": ["a", "b"]},
        "scalar": "text",
    }

    result = remap_file_link_paths(
        inputs,
        source_project_uuid=src_uuid,
        destination_project_uuid=f"{faker.uuid4()}",
        nodes_map=nodes_map,
    )
    assert result == inputs


def test_remap_file_link_paths_none_and_empty(faker: Faker):
    nodes_map: NodesMap = {f"{faker.uuid4()}": f"{faker.uuid4()}"}

    assert (
        remap_file_link_paths(
            None,
            source_project_uuid=f"{faker.uuid4()}",
            destination_project_uuid=f"{faker.uuid4()}",
            nodes_map=nodes_map,
        )
        is None
    )
    assert (
        remap_file_link_paths(
            {},
            source_project_uuid=f"{faker.uuid4()}",
            destination_project_uuid=f"{faker.uuid4()}",
            nodes_map=nodes_map,
        )
        == {}
    )
