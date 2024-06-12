from typing import Any

import pytest
from models_library.projects import ProjectType as ml_project_type
from simcore_postgres_database.models.projects import ProjectType as pg_project_type
from simcore_service_webserver.projects.utils import (
    NodeDict,
    find_changed_node_keys,
    get_frontend_node_outputs_changes,
)


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
