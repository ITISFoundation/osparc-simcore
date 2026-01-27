from dataclasses import dataclass
from typing import Any

import pytest
from simcore_service_director_v2.utils.dict_utils import (
    get_leaf_key_paths,
    nested_update,
)


@dataclass(
    frozen=True,
)
class MergeStructureTestParams:
    a: dict[str, Any]
    b: dict[str, Any]
    include: tuple[list[str], ...]
    expected_dict: dict[str, Any]


@pytest.mark.parametrize(
    "test_params",
    [
        MergeStructureTestParams(
            a={},
            b={},
            include=(["a", "key", "path"], ["another"]),
            expected_dict={},
        ),
        MergeStructureTestParams(
            a={"labels": ["1", "2"]},
            b={"labels": ["3", "2"]},
            include=(["labels"],),
            expected_dict={"labels": ["1", "2", "3", "2"]},
        ),
        MergeStructureTestParams(
            a={"labels": {"my_label": "label_value1"}},
            b={"labels": {"my_label": "label_value2"}},
            include=(["labels"],),
            expected_dict={"labels": {"my_label": "label_value2"}},
        ),
        MergeStructureTestParams(
            a={"labels": {"my_label1": "label_value1"}},
            b={"labels": {"my_label2": "label_value2"}},
            include=(["labels"],),
            expected_dict={"labels": {"my_label1": "label_value1", "my_label2": "label_value2"}},
        ),
        MergeStructureTestParams(
            a={
                "labels": {"my_label1": "label_value1"},
                "entry1": {"entry2": {"entry3": "value"}},
            },
            b={"labels": {"my_label2": "label_value2"}},
            include=(["labels"], ["entry1", "entry2"]),
            expected_dict={
                "labels": {"my_label1": "label_value1", "my_label2": "label_value2"},
                "entry1": {"entry2": {"entry3": "value"}},
            },
        ),
        MergeStructureTestParams(
            a={
                "labels": {"my_label1": "label_value1"},
                "entry1": {"entry2": {"entry3": "value"}},
            },
            b={
                "labels": {"my_label2": "label_value2"},
                "entry1": {"entry2": {"entry4": "value"}},
            },
            include=(["labels"], ["entry1", "entry2"]),
            expected_dict={
                "labels": {"my_label1": "label_value1", "my_label2": "label_value2"},
                "entry1": {"entry2": {"entry3": "value", "entry4": "value"}},
            },
        ),
        MergeStructureTestParams(
            a={
                "labels": {"my_label1": "label_value1"},
                "entry1": {"entry2": {"entry3": 3}},
            },
            b={
                "labels": {"my_label2": "label_value2"},
                "entry1": {"entry2": {"entry3": 5}},
            },
            include=(["labels"], ["entry1", "entry2", "entry3"]),
            expected_dict={
                "labels": {"my_label1": "label_value1", "my_label2": "label_value2"},
                "entry1": {"entry2": {"entry3": 5}},
            },
        ),
        MergeStructureTestParams(
            a={
                "a": {"aa": "1", "bb": {"aaa": 4}},
                "b": {"cc": {"change_me": 3, "keep_me": 4}},
            },
            b={
                "b": {"cc": {"change_me": 5}},
            },
            include=(["b", "cc", "change_me"],),
            expected_dict={
                "a": {"aa": "1", "bb": {"aaa": 4}},
                "b": {"cc": {"change_me": 5, "keep_me": 4}},
            },
        ),
        MergeStructureTestParams(
            a={
                "a": {"aa": "1", "bb": {"aaa": 4}},
                "b": {"cc": {"change_me": [3], "keep_me": 4}},
            },
            b={
                "b": {"cc": {"change_me": [1]}},
            },
            include=(["b", "cc", "change_me"],),
            expected_dict={
                "a": {"aa": "1", "bb": {"aaa": 4}},
                "b": {"cc": {"change_me": [3, 1], "keep_me": 4}},
            },
        ),
    ],
)
def test_merge_complex_structures(test_params: MergeStructureTestParams):
    returned_struct = nested_update(
        test_params.a,
        test_params.b,
        include=test_params.include,
    )
    assert returned_struct is not None
    assert returned_struct == test_params.expected_dict


@dataclass(
    frozen=True,
)
class GetLeafKeyPathsTestParams:
    data: dict[str, Any]
    expected: tuple[list[str], ...]


@pytest.mark.parametrize(
    "test_params",
    [
        GetLeafKeyPathsTestParams(
            data={
                "a": 3,
                "b": 3,
                "c": {
                    "x": 12,
                    "y": "hello",
                    "z": {
                        "alpha": 2,
                        "beta": {},
                        "gama": 0,
                    },
                },
                "d": {},
            },
            expected=(
                ["a"],
                ["b"],
                ["c", "x"],
                ["c", "y"],
                ["c", "z", "alpha"],
                ["c", "z", "beta"],
                ["c", "z", "gama"],
                ["d"],
            ),
        ),
        GetLeafKeyPathsTestParams(
            data={
                "a": 3,
                "c": {
                    "p": 12,
                    "h": {
                        "k": 2,
                    },
                },
            },
            expected=(
                ["a"],
                ["c", "p"],
                ["c", "h", "k"],
            ),
        ),
    ],
)
def test_get_leaf_key_paths(test_params: GetLeafKeyPathsTestParams) -> None:
    assert get_leaf_key_paths(test_params.data) == test_params.expected
