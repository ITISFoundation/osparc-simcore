# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import json
import logging
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from models_library.projects import Project
from models_library.projects import ProjectType as ml_project_type
from models_library.projects_nodes_io import NodeID
from models_library.services import ServiceKey
from simcore_postgres_database.models.projects import ProjectType as pg_project_type
from simcore_service_webserver.projects._nodes_service import (
    project_get_depending_nodes,
)
from simcore_service_webserver.projects._projects_service_utils import (
    clone_project_document,
    default_copy_project_name,
    find_changed_node_keys,
)
from simcore_service_webserver.projects.models import ProjectDict

_logger = logging.getLogger(__name__)


# NOTE: InputTypes/OutputTypes that are NOT links
_NOT_IO_LINK_TYPES_TUPLE = (str, int, float, bool)


def any_node_inputs_changed(
    updated_project: ProjectDict, current_project: ProjectDict
) -> bool:
    """Returns true if any change is detected in the node inputs of the updated project

    Based on the limitation we are detecting with this check, new nodes only account for
    a "change" if they add link inputs.
    """
    # NOTE: should not raise exceptions in production

    project_uuid = current_project["uuid"]

    assert (  # nosec
        updated_project.get("uuid") == project_uuid
    ), f"Expected same project, got {updated_project.get('uuid')}!={project_uuid}"

    assert (  # nosec
        "workbench" in updated_project
    ), f"expected validated model but got {list(updated_project.keys())=}"

    assert (  # nosec
        "workbench" in current_project
    ), f"expected validated model but got {list(current_project.keys())=}"

    # detect input changes in existing nodes
    for node_id, updated_node in updated_project["workbench"].items():
        if current_node := current_project["workbench"].get(node_id, None):
            if (updated_inputs := updated_node.get("inputs")) != current_node.get(
                "inputs"
            ):
                _logger.debug(
                    "Change detected in projects[%s].workbench[%s].%s",
                    f"{project_uuid=}",
                    f"{node_id=}",
                    f"{updated_inputs=}",
                )
                return True

        else:
            # for new nodes, detect only added link
            for input_name, input_value in updated_node.get("inputs", {}).items():
                # TODO: how to ensure this list of "links types" is up-to-date!??
                # Anything outside of the PRIMITIVE_TYPES_TUPLE, is interpreted as links
                # that node-ports need to handle. This is a simpler check with ProjectDict
                # since otherwise test will require constructing BaseModels on input_values
                if not isinstance(input_value, _NOT_IO_LINK_TYPES_TUPLE):
                    _logger.debug(
                        "Change detected in projects[%s].workbench[%s].inputs[%s]=%s. Link was added.",
                        f"{project_uuid=}",
                        f"{node_id=}",
                        f"{input_name}",
                        f"{input_value}",
                    )
                    return True
    return False


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


@pytest.mark.parametrize(
    "dict_a, dict_b, expected_changes",
    [
        pytest.param(
            {"state": "PUBLISHED"},
            {"state": "PUBLISHED"},
            {},
            id="same entry",
        ),
        pytest.param(
            {"state": "PUBLISHED"},
            {"inputs": {"in_1": 1, "in_2": 4}},
            {"inputs": {"in_1": 1, "in_2": 4}},
            id="new entry",
        ),
        pytest.param({"state": "PUBLISHED"}, {}, {}, id="empty patch"),
        pytest.param(
            {"state": "PUBLISHED"},
            {"state": "RUNNING"},
            {"state": "RUNNING"},
            id="patch with new data",
        ),
        pytest.param(
            {"inputs": {"in_1": 1, "in_2": 4}},
            {"inputs": {"in_2": 5}},
            {"inputs": {"in_1": 1, "in_2": 5}},
            id="patch with new nested data",
        ),
        pytest.param(
            {"inputs": {"in_1": 1, "in_2": 4}},
            {"inputs": {"in_1": 1, "in_2": 4, "in_6": "new_entry"}},
            {"inputs": {"in_6": "new_entry"}},
            id="patch with additional nested data",
        ),
        pytest.param(
            {
                "inputs": {
                    "in_1": {"some_file": {"etag": "lkjflsdkjfslkdj"}},
                    "in_2": 4,
                }
            },
            {
                "inputs": {
                    "in_1": {"some_file": {"etag": "newEtag"}},
                    "in_2": 4,
                }
            },
            {
                "inputs": {
                    "in_1": {"some_file": {"etag": "newEtag"}},
                }
            },
            id="patch with 2x nested new data",
        ),
        pytest.param(
            {"inputs": {"in_1": 1}},
            {
                "inputs": {
                    "in_1": {
                        "nodeUuid": "c374e5ba-fc42-5c40-ae74-df7ef337f597",
                        "output": "out_1",
                    }
                }
            },
            {
                "inputs": {
                    "in_1": {
                        "nodeUuid": "c374e5ba-fc42-5c40-ae74-df7ef337f597",
                        "output": "out_1",
                    }
                }
            },
            id="patch with new data type change int -> dict",
        ),
        pytest.param(
            {
                "inputs": {
                    "in_1": {
                        "nodeUuid": "c374e5ba-fc42-5c40-ae74-df7ef337f597",
                        "output": "out_1",
                    }
                }
            },
            {"inputs": {"in_1": 1}},
            {"inputs": {"in_1": 1}},
            id="patch with new data type change dict -> int",
        ),
        pytest.param(
            {"remove_entries_in_dict": {"outputs": {"out_1": 123, "out_3": True}}},
            {"remove_entries_in_dict": {"outputs": {}}},
            {"remove_entries_in_dict": {"outputs": {"out_1": 123, "out_3": True}}},
            id="removal of data",
        ),
    ],
)
def test_find_changed_node_keys(
    dict_a: dict[str, Any], dict_b: dict[str, Any], expected_changes: dict[str, Any]
):
    assert (
        find_changed_node_keys(dict_a, dict_b, look_for_removed_keys=False)
        == expected_changes
    )


@pytest.mark.parametrize(
    "dict_a, dict_b, expected_changes",
    [
        pytest.param(
            {
                "key": "simcore/services/frontend/file-picker",
                "outputs": {"outFile": {"store": 0}},
                "runHash": None,
            },
            {
                "outputs": {"outFile": {"store": "0"}},
                "runHash": None,
            },
            {},
            id="cast store to string avoids triggering",
        ),
        pytest.param(
            {
                "key": "simcore/services/frontend/file-picker",
                "version": "1.0.0",
                "label": "File Picker",
                "inputs": {},
                "inputsUnits": {},
                "inputNodes": [],
                "parent": None,
                "thumbnail": "",
                "outputs": {},
                "progress": 0,
                "runHash": None,
            },
            {"outputs": {}, "runHash": None},
            # the result of the function is correct
            {},
            id="removing a file from file picker",
        ),
    ],
)
def test_find_changed_node_keys_file_picker_case(
    dict_a: dict[str, Any], dict_b: dict[str, Any], expected_changes: dict[str, Any]
):
    assert (
        find_changed_node_keys(dict_a, dict_b, look_for_removed_keys=False)
        == expected_changes
    )


_SUPPORTED_FRONTEND_KEYS: set[ServiceKey] = {
    ServiceKey("simcore/services/frontend/file-picker"),
}


class NodeDict(TypedDict, total=False):
    key: ServiceKey | None
    outputs: dict[str, Any] | None


def get_frontend_node_outputs_changes(
    new_node: NodeDict, old_node: NodeDict
) -> set[str]:
    changed_keys: set[str] = set()

    # ANE: if node changes it's outputs and is not a supported
    # frontend type, return no frontend changes
    old_key, new_key = old_node.get("key"), new_node.get("key")
    if old_key == new_key and new_key not in _SUPPORTED_FRONTEND_KEYS:
        return set()

    _logger.debug("Comparing nodes %s %s", new_node, old_node)

    def _check_for_changes(d1: dict[str, Any], d2: dict[str, Any]) -> None:
        """
        Checks if d1's values have changed compared to d2's.
        NOTE: Does not guarantee that d2's values have changed
        compare to d1's.
        """
        for k, v in d1.items():
            if k not in d2:
                changed_keys.add(k)
                continue
            if v != d2[k]:
                changed_keys.add(k)

    new_outputs: dict[str, Any] = new_node.get("outputs", {}) or {}
    old_outputs: dict[str, Any] = old_node.get("outputs", {}) or {}

    _check_for_changes(new_outputs, old_outputs)
    _check_for_changes(old_outputs, new_outputs)

    return changed_keys


@pytest.mark.parametrize(
    "new_node, old_node, expected",
    [
        pytest.param(
            {
                "key": "simcore/services/frontend/file-picker",
                "version": "1.0.0",
                "label": "test_local.log",
                "inputs": {},
                "inputsUnits": {},
                "inputNodes": [],
                "parent": None,
                "thumbnail": "",
                "outputs": {
                    "outFile": {
                        "store": 0,
                        "dataset": "6b96a29a-d73c-11ec-943f-02420a000008",
                        "path": "6b96a29a-d73c-11ec-943f-02420a000008/2b5cc601-95dd-4c67-b6b9-c4cf3adcd4d1/test_local.log",
                        "label": "test_local.log",
                    }
                },
                "progress": 100,
            },
            {
                "key": "simcore/services/frontend/file-picker",
                "version": "1.0.0",
                "label": "File Picker",
                "inputs": {},
                "inputsUnits": {},
                "inputNodes": [],
                "parent": None,
                "thumbnail": "",
                "outputs": {},
                "progress": 0,
                "runHash": None,
            },
            {"outFile"},
            id="file-picker outputs changed (file was added)",
        ),
        pytest.param(
            {
                "key": "simcore/services/frontend/file-picker",
                "version": "1.0.0",
                "label": "File Picker",
                "inputs": {},
                "inputsUnits": {},
                "inputNodes": [],
                "parent": None,
                "thumbnail": "",
                "outputs": {},
                "progress": 0,
            },
            {
                "key": "simcore/services/frontend/file-picker",
                "version": "1.0.0",
                "label": "test_local.log",
                "inputs": {},
                "inputsUnits": {},
                "inputNodes": [],
                "parent": None,
                "thumbnail": "",
                "outputs": {
                    "outFile": {
                        "store": "0",
                        "path": "6b96a29a-d73c-11ec-943f-02420a000008/2b5cc601-95dd-4c67-b6b9-c4cf3adcd4d1/test_local.log",
                        "label": "test_local.log",
                        "dataset": "6b96a29a-d73c-11ec-943f-02420a000008",
                    }
                },
                "progress": 100,
                "runHash": None,
            },
            {"outFile"},
            id="file-picker outputs changed (file was removed)",
        ),
        pytest.param(
            {
                "key": "simcore/services/frontend/file-picker",
                "version": "1.0.0",
                "label": "File Picker",
                "inputs": {},
                "inputsUnits": {},
                "inputNodes": [],
                "parent": None,
                "thumbnail": "",
                "outputs": {
                    "outFile": {
                        "store": "0",
                        "path": "6b96a29a-d73c-11ec-943f-02420a000008/2b5cc601-95dd-4c67-b6b9-c4cf3adcd4d1/test_local.log",
                        "label": "test_local.log",
                        "dataset": "6b96a29a-d73c-11ec-943f-02420a000008",
                    }
                },
                "progress": 0,
            },
            {
                "key": "simcore/services/frontend/file-picker",
                "version": "1.0.0",
                "label": "test_local.log",
                "inputs": {},
                "inputsUnits": {},
                "inputNodes": [],
                "parent": None,
                "thumbnail": "",
                "outputs": {
                    "outFile": {
                        "store": "0",
                        "path": "6b96a29a-d73c-11ec-943f-02420a000008/2b5cc601-95dd-4c67-b6b9-c4cf3adcd4d1/renamed_test_local2.log",  # <--- different
                        "label": "renamed_test_local2.log",  # <--- different
                        "dataset": "6b96a29a-d73c-11ec-943f-02420a000008",
                    }
                },
                "progress": 100,
                "runHash": None,
            },
            {"outFile"},
            id="file-picker outputs changed (file was replaced)",
        ),
        pytest.param(
            {
                "key": "simcore/services/frontend/file-picker",
                "version": "1.0.0",
                "label": "test_local.log",
                "inputs": {},
                "inputsUnits": {},
                "inputNodes": [],
                "parent": None,
                "thumbnail": "",
                "outputs": {
                    "outFile": {
                        "store": "0",
                        "path": "6b96a29a-d73c-11ec-943f-02420a000008/2b5cc601-95dd-4c67-b6b9-c4cf3adcd4d1/test_local.log",
                        "label": "test_local.log",
                        "dataset": "6b96a29a-d73c-11ec-943f-02420a000008",
                    }
                },
                "progress": 100,
            },
            {
                "key": "simcore/services/frontend/file-picker",
                "version": "1.0.0",
                "label": "test_local.log",
                "inputs": {},
                "inputsUnits": {},
                "inputNodes": [],
                "parent": None,
                "thumbnail": "",
                "outputs": {
                    "outFile": {
                        "store": "0",
                        "path": "6b96a29a-d73c-11ec-943f-02420a000008/2b5cc601-95dd-4c67-b6b9-c4cf3adcd4d1/test_local.log",
                        "label": "test_local.log",
                        "dataset": "6b96a29a-d73c-11ec-943f-02420a000008",
                    }
                },
                "progress": 100,
                "runHash": None,
            },
            set(),
            id="file-picker outputs did not change",
        ),
        pytest.param(
            {"key": "simcore/services/frontend/file-picker", "outputs": None},
            {"key": "simcore/services/dynamic/different", "outputs": None},
            set(),
            id="replacing frontend-type with",
        ),
        pytest.param(
            {"key": "simcore/services/dynamic/different", "outputs": None},
            {
                "key": "simcore/services/frontend/file-picker",
                "outputs": {
                    "outFile": {
                        "store": "0",
                        "path": "6b96a29a-d73c-11ec-943f-02420a000008/2b5cc601-95dd-4c67-b6b9-c4cf3adcd4d1/test_local.log",
                        "label": "test_local.log",
                        "dataset": "6b96a29a-d73c-11ec-943f-02420a000008",
                    }
                },
            },
            {"outFile"},
            id="replaced not fronted type node with a frontend type node",
        ),
        pytest.param(
            {"key": "simcore/services/frontend/file-picker", "outputs": {}},
            {"key": "simcore/services/frontend/file-picker", "outputs": None},
            set(),
            id="no and not existing outputs trigger",
        ),
        pytest.param(
            {},
            {},
            set(),
            id="all keys missing do not trigger",
        ),
        pytest.param(
            {"a": "key"},
            {"another": "key"},
            set(),
            id="different keys but missing key and outputs do not trigger",
        ),
        pytest.param(
            {"key": "simcore/services/frontend/file-picker"},
            {"key": "simcore/services/frontend/file-picker"},
            set(),
            id="missing outputs do not trigger",
        ),
    ],
)
def test_did_node_outputs_change(
    new_node: NodeDict, old_node: NodeDict, expected: set[str]
) -> None:
    assert (
        get_frontend_node_outputs_changes(new_node=new_node, old_node=old_node)
        == expected
    )


def test_project_type_in_models_package_same_as_in_postgres_database_package():

    # pylint: disable=no-member
    assert (
        ml_project_type.__members__.keys() == pg_project_type.__members__.keys()
    ), f"The enum in models_library package and postgres package shall have the same values. models_pck: {ml_project_type.__members__}, postgres_pck: {pg_project_type.__members__}"
