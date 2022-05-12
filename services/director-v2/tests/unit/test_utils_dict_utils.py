from dataclasses import dataclass
from typing import Any

import pytest
from simcore_service_director_v2.utils.dict_utils import nested_update


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
            expected_dict={
                "labels": {"my_label1": "label_value1", "my_label2": "label_value2"}
            },
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
