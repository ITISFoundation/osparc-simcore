from typing import Any, Dict

import pytest
from simcore_service_webserver.projects.projects_utils import (
    find_changed_dict_keys,
    get_node_outputs_changes,
    OutputsChanges,
)


@pytest.mark.parametrize(
    "dict_a, dict_b, exp_changes",
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
            {"remove_entries_in_dict": {"outputs": {"out_1": 123, "out_3": True}}},
            {"remove_entries_in_dict": {"outputs": {}}},
            {"remove_entries_in_dict": {"outputs": {"out_1": 123, "out_3": True}}},
            id="removal of data",
        ),
    ],
)
def test_find_changed_dict_keys(
    dict_a: Dict[str, Any], dict_b: Dict[str, Any], exp_changes: Dict[str, Any]
):
    assert (
        find_changed_dict_keys(dict_a, dict_b, look_for_removed_keys=False)
        == exp_changes
    )


@pytest.mark.parametrize(
    "dict_a, dict_b, exp_changes",
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
def test_find_changed_dict_keys_file_picker_case(
    dict_a: Dict[str, Any], dict_b: Dict[str, Any], exp_changes: Dict[str, Any]
):
    assert (
        find_changed_dict_keys(dict_a, dict_b, look_for_removed_keys=False)
        == exp_changes
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
            OutputsChanges(True, {"outFile"}),
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
            OutputsChanges(True, {"outFile"}),
            id="file-picker outputs changed (file was removed)",
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
            OutputsChanges(False, set()),
            id="file-picker outputs did not change",
        ),
        pytest.param(
            {"key": "simcore/services/frontend/file-picker", "outputs": None},
            {"key": "simcore/services/frontend/diffrenet", "outputs": None},
            OutputsChanges(False, set()),
            id="different keys do not trigger",
        ),
        pytest.param(
            {"key": "simcore/services/frontend/file-picker", "outputs": {}},
            {"key": "simcore/services/frontend/file-picker", "outputs": None},
            OutputsChanges(True, set()),
            id="no and not existing outputs trigger",
        ),
        pytest.param(
            {},
            {},
            OutputsChanges(False, set()),
            id="all keys missing do not trigger",
        ),
        pytest.param(
            {"a": "key"},
            {"another": "key"},
            OutputsChanges(False, set()),
            id="different keys but missing key and outputs do not trigger",
        ),
        pytest.param(
            {"key": "simcore/services/frontend/file-picker"},
            {"key": "simcore/services/frontend/file-picker"},
            OutputsChanges(False, set()),
            id="missing outputs do not trigger",
        ),
    ],
)
def test_did_node_outputs_change(
    new_node: Dict[str, Any], old_node: Dict[str, Any], expected: OutputsChanges
) -> None:
    assert (
        get_node_outputs_changes(
            new_node=new_node,
            old_node=old_node,
            filter_keys={"simcore/services/frontend/file-picker"},
        )
        == expected
    )
