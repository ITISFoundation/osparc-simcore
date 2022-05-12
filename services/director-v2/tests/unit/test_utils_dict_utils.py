from dataclasses import dataclass
from typing import Any

import pytest
from simcore_service_director_v2.utils.dict_utils import merge_extend


@dataclass(
    frozen=True,
)
class MergeStructureTestParams:
    struct_a: dict[str, Any]
    struct_b: dict[str, Any]
    extendable_arrays: tuple[list[str], ...]
    extendable_dicts: tuple[list[str], ...]
    expected_result_struct: dict[str, Any]


@pytest.mark.parametrize(
    "test_params",
    [
        MergeStructureTestParams(
            {"labels": ["1", "2"]},
            {"labels": ["3", "2"]},
            (["labels"],),
            (),
            {"labels": ["1", "2", "3", "2"]},
        )
    ],
)
def test_merge_complex_structures(test_params: MergeStructureTestParams):
    returned_struct = merge_extend(
        test_params.struct_a,
        test_params.struct_b,
        extendable_array_keys=test_params.extendable_arrays,
        extendable_dict_keys=test_params.extendable_dicts,
    )
    assert returned_struct
    assert returned_struct == test_params.expected_result_struct
